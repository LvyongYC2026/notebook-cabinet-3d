// Display-only conversion: model geometry and metadata remain in millimetres.
const centimetreNumber = new Intl.NumberFormat('zh-CN', {
  useGrouping: false,
  maximumFractionDigits: 4
});

function numericValue(value) {
  if (typeof value !== 'number' && typeof value !== 'string') return NaN;
  if (typeof value === 'string' && !value.trim()) return NaN;
  return Number(typeof value === 'string' ? value.replace(/,/g, '').trim() : value);
}

function formatNumber(value) {
  return Number.isFinite(value) ? centimetreNumber.format(Object.is(value, -0) ? 0 : value) : '—';
}

/** Format a millimetre value as centimetres, without a unit suffix. */
export function formatLengthCm(valueMm) {
  return formatNumber(numericValue(valueMm) / 10);
}

const numberSource = String.raw`[+−-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)`;
const unitSource = String.raw`(?:毫米|厘米|mm(?![a-z²³]|\s*\^[23])|cm(?![a-z²³]|\s*\^[23]))`;
const separatorSource = String.raw`\s*(?:[×xX*+±–—~～/、，,]|至|到|-)\s*(?:(?:长度|宽度|深度|高度|厚度|直径|长|宽|深|高|厚)\s*[:：=]?\s*)?`;
const valueSource = `${numberSource}(?:\\s*${unitSource})?`;
const expressionPattern = new RegExp(
  `(?<![A-Za-z_\\d.])(?:(${unitSource})\\s*[:：]?\\s*)?(${valueSource}(?:${separatorSource}${valueSource})*)`,
  'gi'
);
const radiusDiameterPattern = new RegExp(`(?<![A-Za-z_\\d])([RrØ⌀Φφ])\\s*(${numberSource})\\s*(${unitSource})`, 'g');
const valuePattern = new RegExp(`(${numberSource})(?:\\s*(${unitSource}))?`, 'gi');
const inchPattern = new RegExp(
  `(?<![A-Za-z_\\d.])(${numberSource})\\s*(?:英寸|寸)(?:\\s*(?:[（(]对角线[）)]|对角线))?`,
  'g'
);

function isMillimetres(unit) {
  return /^(?:毫米|mm)$/i.test(unit);
}

/**
 * Convert explicitly unit-bearing prose to cm, including dimensions, ranges,
 * shared units and units before numbers. Existing cm values are not rescaled.
 * Numbers without length units (degrees, volts, counts, etc.) stay unchanged.
 */
export function lengthTextToCm(text) {
  let result = String(text ?? '');
  result = result.replace(radiusDiameterPattern, (match, symbol, value, unit) => `${symbol}${formatNumber(numericValue(value.replace('−', '-')) / (isMillimetres(unit) ? 10 : 1))} cm`);
  result = result.replace(inchPattern, (match, value, offset, source) => {
    const preceding = source.slice(0, offset);
    const hasDiagonalLabel = /对角线(?:长度)?\s*(?:为|约|为约|[:：])?\s*$/.test(preceding);
    return `${hasDiagonalLabel ? '' : '对角线'}${formatNumber(numericValue(value.replace('−', '-')) * 2.54)} cm`;
  });
  return result.replace(expressionPattern, (match, prefixUnit, expression) => {
    const values = [...expression.matchAll(valuePattern)];
    if (!prefixUnit && !values.some(value => value[2])) return match;
    let index = 0;
    const converted = expression.replace(valuePattern, (value, digits, ownUnit) => {
      const nextUnit = values.slice(index + 1).find(next => next[2])?.[2];
      const previousUnit = values.slice(0, index).reverse().find(previous => previous[2])?.[2];
      const unit = ownUnit || prefixUnit || nextUnit || previousUnit;
      index++;
      const number = numericValue(digits.replace('−', '-'));
      const formatted = formatNumber(isMillimetres(unit) ? number / 10 : number);
      return digits.startsWith('+') ? `+${formatted}` : formatted;
    });
    return `${converted} cm`;
  });
}
