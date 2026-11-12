// Amounts are whole won. Decimal percentages are represented as exact fractions.
export function parseWon(value) {
  const match = String(value ?? '').trim().match(/^((?:\d{1,3}(?:,\d{3})+|\d+))\s*원?(?:\s*\([^)\d]*\))?$/)
  if (!match) return null
  const amount = Number(match[1].replaceAll(',', ''))
  return Number.isSafeInteger(amount) ? amount : null
}

function percent(value, label) {
  const match = String(value).trim().match(/^(\d{1,3})(?:\.(\d{1,10}))?$/)
  if (!match || Number(value) <= 0) throw new Error(label + '을(를) 입력하세요.')
  const fraction = match[2] ?? ''
  return [BigInt(match[1] + fraction), 100n * 10n ** BigInt(fraction.length)]
}

const ceil = (numerator, denominator) => (numerator + denominator - 1n) / denominator

export function calculateBid(input) {
  const base = parseWon(input.base)
  const a = input.useA || input.profile ? parseWon(input.a) : 0
  const cost = input.useCost ? parseWon(input.cost) : null
  const bid = parseWon(input.bid)
  if (!base || a === null || a >= base) throw new Error('기초금액과 A값을 확인하세요. A값이 0원이면 0을 입력하세요.')
  if (input.useCost && (!cost || cost > base)) throw new Error('기초금액 중 순공사원가를 확인하세요.')
  if (String(input.bid ?? '').trim() && !bid) throw new Error('검토할 입찰가격을 원 단위로 입력하세요.')

  const [rate, divisor] = percent(input.rate, '낙찰하한율')
  if (rate > divisor) throw new Error('낙찰하한율은 100% 이하여야 합니다.')
  const explicit = String(input.expected ?? '').trim()
  let price, scale
  if (explicit) {
    const expected = parseWon(explicit)
    if (!expected) throw new Error('예정가격을 원 단위로 확인하세요.')
    price = BigInt(expected)
    scale = 1n
  } else {
    const [adjustment, denominator] = percent(input.adjustment, '사정률')
    price = BigInt(base) * adjustment
    scale = denominator
  }
  const adjusted = price - BigInt(a) * scale
  if (adjusted <= 0n) throw new Error('예정가격은 A값보다 커야 합니다.')
  if (input.useCost && price >= 10000000000n * scale) {
    throw new Error('예정가격이 100억원 이상입니다. 공고문을 확인하고 98% 기준 적용 여부를 다시 선택하세요.')
  }

  const floorA = input.useA ? BigInt(a) * scale : 0n
  const rateFloor = ceil((price - floorA) * rate + floorA * divisor, scale * divisor)
  const adjustedCost = input.useCost ? ceil(BigInt(cost) * price, BigInt(base) * scale) : null
  const costFloor = adjustedCost === null ? null : ceil(adjustedCost * 98n, 100n)
  const minimum = costFloor !== null && costFloor > rateFloor ? costFloor : rateFloor
  if (!Number.isSafeInteger(Number(minimum)) || price > BigInt(Number.MAX_SAFE_INTEGER) * scale) {
    throw new Error('금액이 계산 범위를 초과했습니다.')
  }
  const evaluated = BigInt(bid ?? Number(minimum))
  const withinExpected = evaluated * scale <= price
  const adjustedBid = (evaluated - BigInt(a)) * scale
  let score = null
  if (input.profile && withinExpected && adjustedBid >= 0n) {
    const { points, center, multiplier, fixedRate, fixedScore, minimumScore } = input.profile
    // Ratios use units of 0.0001, equivalent to 0.01 percentage points.
    const ratioUnits = (2n * adjustedBid * 10000n + adjusted) / (2n * adjusted)
    const fixed = adjustedBid * 10000n >= adjusted * BigInt(fixedRate)
    score = fixed ? fixedScore : Math.max(minimumScore, points - multiplier * Math.abs(center - Number(ratioUnits)) / 100)
    score = Number(score.toFixed(2))
  }
  return {
    expected: Number(price / scale) + Number(price % scale) / Number(scale),
    rateFloor: Number(rateFloor), adjustedCost: adjustedCost === null ? null : Number(adjustedCost),
    costFloor: costFloor === null ? null : Number(costFloor), minimum: Number(minimum),
    evaluated: Number(evaluated), withinExpected, passesRate: evaluated >= rateFloor,
    passesCost: costFloor === null ? null : evaluated >= costFloor, score,
  }
}

// Reference profiles from the supplied workbooks. Selection is explicit.
const profiles = {
  local70: { points: 70, center: 8800, multiplier: 4, fixedRate: 8925, fixedScore: 65, minimumScore: 0 },
  pps70: { points: 70, center: 9000, multiplier: 20, fixedRate: 9025, fixedScore: 65, minimumScore: 0 },
  pps50: { points: 50, center: 9000, multiplier: 2, fixedRate: 9250, fixedScore: 45, minimumScore: 0 },
  local80: { points: 80, center: 9000, multiplier: 20, fixedRate: 9025, fixedScore: 75, minimumScore: 2 },
}

export function resolveLowerRate(bid, titleRate) {
  const description = String(bid.raw_description ?? '')
  const field = label => description.match(new RegExp('^[^\\S\\r\\n]*' + label + '[^\\S\\r\\n]*[:：][^\\S\\r\\n]*([^\\r\\n]*)', 'm'))?.[1].trim()
  const candidates = [bid.lower_rate, field('낙찰하한율'), field('입찰하한율'), titleRate]
  for (const candidate of candidates) {
    const value = String(candidate ?? '').trim().match(/^(\d{1,3}(?:\.\d+)?)\s*%?$/)?.[1]
    if (Number(value) > 0 && Number(value) <= 100) return value
  }

  const kind = String(bid.task_type || field('업무구분') || field('업종유형') || '').trim()
  if (!['공사', '시설공사', '전문공사', '종합공사'].includes(kind)) return ''
  const estimated = parseWon(field('추정가격'))
  if (!estimated || estimated >= 10_000_000_000) return ''
  if (estimated < 1_000_000_000) return '89.745'
  if (estimated < 5_000_000_000) return '88.745'
  return '87.495'
}

export function mountCalculator(host, bid, titleRate) {
  host.innerHTML = `
    <form class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
      <label>기초금액 (원)<input name="base" inputmode="numeric" class="block w-full border rounded p-2" required></label>
      <label>A값 (원)<input name="a" inputmode="numeric" class="block w-full border rounded p-2"></label>
      <label class="sm:col-span-2">예비가격 기초금액 중 순공사원가 (원)<input name="cost" inputmode="numeric" class="block w-full border rounded p-2"></label>
      <label>사정률 (기초금액 대비 %)<input name="adjustment" inputmode="decimal" placeholder="예: 99.5679" required class="block w-full border rounded p-2"></label>
      <label>공고 낙찰하한율 (%)<input name="rate" inputmode="decimal" class="block w-full border rounded p-2" required></label>
      <label>검토할 입찰가격 (원, 선택)<input name="bid" inputmode="numeric" class="block w-full border rounded p-2"></label>
      <label>하한율 산식<select name="useA" class="block w-full border rounded p-2" required>
        <option value="">공고문 기준 선택</option><option value="yes">A값 차감 후 적용</option><option value="no">예정가격에 직접 적용</option>
      </select></label>
      <label>순공사원가 98% 기준<select name="useCost" class="block w-full border rounded p-2" required>
        <option value="">공고문 기준 선택</option><option value="yes">적용</option><option value="no">미적용</option>
      </select></label>
      <label class="sm:col-span-2">가격점수 산식<select name="profile" class="block w-full border rounded p-2">
        <option value="">가격점수 계산 생략</option>
        <option value="local70">10~50억원 지자체·조달 외 (70점, 88%, 계수 4)</option>
        <option value="pps70">10~50억원 조달청 (70점, 90%, 계수 20)</option>
        <option value="pps50">50~100억원 조달청 (50점, 90%, 계수 2)</option>
        <option value="local80">4~10억원 지자체 (80점, 90%, 계수 20)</option>
      </select></label>
      <p class="sm:col-span-2 text-gray-600">예상 예정가격 = 기초금액 × 사정률 ÷ 100. 예: 99.5679, 100.2439, 101.5029. 산식과 하한율은 공고문에서 확인하세요.</p>
      <button class="sm:col-span-2 bg-blue-600 text-white rounded p-2">입찰가 계산</button>
      <div class="sm:col-span-2 whitespace-pre-line rounded bg-blue-50 p-3" role="status" hidden></div>
    </form>`
  const form = host.querySelector('form')
  const output = host.querySelector('[role="status"]')
  const kind = String(bid.task_type ?? '').trim()
  const descriptionKind = String(bid.raw_description ?? '').match(/^[^\S\r\n]*(?:업무구분|업종유형)[^\S\r\n]*[:：][^\S\r\n]*([^\r\n]+)/m)?.[1].trim()
  const isGoods = /^(?:물품(?:\s*구매)?|구매|물품\s*\(구매\)|구매\s*\(물품\))$/.test(kind || descriptionKind || '')
  if (isGoods) {
    for (const name of ['a', 'cost', 'useA', 'useCost', 'profile']) {
      const input = form.elements[name]
      input.required = false
      input.disabled = true
      input.closest('label').hidden = true
    }
  }

  for (const [name, value] of [['base', bid.base_amount], ['a', bid.a_value], ['cost', bid.pure_cost]]) {
    const amount = parseWon(value)
    form.elements[name].value = amount === null ? '' : amount.toLocaleString('ko-KR')
  }
  if (!isGoods && ['없음', '해당 없음', '해당없음'].includes(String(bid.pure_cost ?? '').trim())) {
    form.elements.useCost.value = 'no'
  }
  form.elements.rate.value = resolveLowerRate(bid, titleRate)
  form.addEventListener('input', () => { output.hidden = true })
  form.addEventListener('submit', (event) => {
    event.preventDefault()
    const fields = Object.fromEntries(new FormData(form))
    try {
      const result = calculateBid({
        ...fields, useA: fields.useA === 'yes', useCost: fields.useCost === 'yes', profile: profiles[fields.profile],
      })
      const won = value => value.toLocaleString('ko-KR', { maximumFractionDigits: 10 }) + '원'
      const pass = value => value ? '충족' : '미달'
      output.textContent = [
        '예상 예정가격 ' + won(result.expected),
        '하한율 기준 금액 ' + won(result.rateFloor),
        result.costFloor === null ? '순공사원가 98% 기준 미적용'
          : '예정가격 중 순공사원가 ' + won(result.adjustedCost) + '\n순공사원가 98% 기준 금액 ' + won(result.costFloor),
        (isGoods ? '투찰가격 ' : '두 기준을 반영한 최소 금액 ') + won(result.minimum),
        '검토 금액 ' + won(result.evaluated) + ' · 하한율 ' + pass(result.passesRate)
          + (result.passesCost === null ? '' : ' · 순공사원가 ' + pass(result.passesCost)),
        !result.withinExpected ? '검토 금액이 예정가격을 초과합니다.'
          : result.score === null ? '' : '가격점수 ' + result.score.toFixed(2) + '점',
      ].filter(Boolean).join('\n')
    } catch (error) {
      output.textContent = error.message
    }
    output.hidden = false
  })
}
