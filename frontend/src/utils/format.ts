/** Battery text. The robot reports a battery only if it has a sensor; -1 / null means "not measured" and is never shown as a number. */
export function batteryLabel(level?: number | null, digits = 0): string {
  return level == null || level < 0 ? 'n/a' : `${level.toFixed(digits)}%`
}

export function hasBattery(level?: number | null): level is number {
  return level != null && level >= 0
}
