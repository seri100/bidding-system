import test from 'node:test'
import assert from 'node:assert/strict'
import {extractDetailUrl} from '../public/static/bid-source.js'
test('detail URL supports same-line and next-line calendar descriptions',()=>{
 const url='https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R26BK01797797&bidPbancOrd=000'
 for(const gap of [' ', '\n', '\r\n  ']) assert.equal(extractDetailUrl('\uc0c1\uc138URL :'+gap+url),url)
 assert.equal(extractDetailUrl('\uc0c1\uc138URL :\n\ubc1c\uc8fc\uae30\uad00 : \uc9c4\uc8fc\uc2dc'),null)
 assert.equal(extractDetailUrl('\uc0c1\uc138URL :\n\n'+url),null)
 assert.equal(extractDetailUrl('\uacf5\uace0\uba85 : \uc2dc\ud5d8'),null)
})
