import test from 'node:test'
import assert from 'node:assert/strict'
import { calculateBid, parseWon } from '../public/static/bid-calculator.js'

const sample = {base: '2,639,967,000', a: '145,983,912', cost: '2,377,272,700',
  adjustment: '100.6089', rate: '86.745', useA: true, useCost: true}
const local70 = {points: 70, center: 8800, multiplier: 4, fixedRate: 8925, fixedScore: 65, minimumScore: 0}

test('workbook example uses the larger floor, with separate whole-won ceilings', () => {
  const result = calculateBid({...sample, profile: local70})
  const expected = 2639967000 * 1.006089
  assert.equal(result.expected, expected)
  assert.equal(result.rateFloor, Math.ceil((expected - 145983912) * .86745 + 145983912))
  assert.equal(result.adjustedCost, 2391747914)
  assert.equal(result.costFloor, 2343912956)
  assert.equal(result.minimum, result.costFloor)
  assert.equal(result.score, 68.24)
  assert.equal(calculateBid({...sample,bid:String(result.minimum-1)}).passesCost,false)
})

test('whole-won ceiling remains exact at a boundary and an entered expected price takes precedence', () => {
  const result=calculateBid({base:'1000',a:'0',cost:'50',expected:'1000',adjustment:'99.3',rate:'80.1',useA:true,useCost:true})
  assert.equal(result.rateFloor,801)
  assert.equal(result.costFloor,49)
  assert.equal(result.minimum,801)
})

test('missing inputs are rejected and 100억원 threshold uses expected price', () => {
  assert.equal(parseWon('공고문 참조'),null)
  assert.throws(() => calculateBid({...sample,a:''}), /A값/)
  assert.throws(() => calculateBid({...sample,cost:''}), /순공사원가/)
  assert.throws(() => calculateBid({...sample,expected:'10000000000'}), /100억원/)
  assert.throws(() => calculateBid({...sample,rate:''}), /낙찰하한율/)
})
