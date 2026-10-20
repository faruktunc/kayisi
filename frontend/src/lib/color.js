// CIE L*a*b* (D65) -> sRGB hex; renk numunesini göstermek için
export function labToHex(L, a, b) {
  const fy = (L + 16) / 116
  const fx = fy + a / 500
  const fz = fy - b / 200
  const inv = (t) => (t ** 3 > 0.008856 ? t ** 3 : (t - 16 / 116) / 7.787)
  const X = 0.95047 * inv(fx)
  const Y = 1.0 * inv(fy)
  const Z = 1.08883 * inv(fz)
  const lin = [
    3.2406 * X - 1.5372 * Y - 0.4986 * Z,
    -0.9689 * X + 1.8758 * Y + 0.0415 * Z,
    0.0557 * X - 0.204 * Y + 1.057 * Z,
  ]
  const gamma = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055)
  return '#' + lin.map((c) => Math.round(Math.min(1, Math.max(0, gamma(c))) * 255).toString(16).padStart(2, '0')).join('')
}
