export function extractDetailUrl(description) {
  const match = String(description || '').match(/^\uc0c1\uc138URL[^\S\r\n]*[:\uff1a][^\S\r\n]*(?:\r?\n[^\S\r\n]*)?(https?:\/\/[^\s<>]+)/m)
  return match ? match[1] : null
}
