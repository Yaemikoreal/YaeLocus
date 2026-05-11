import { describe, it, expect } from 'vitest'
import {
  isValidLat,
  isValidLon,
  parseCoordinate,
  validateFile,
  formatCoords,
  formatFileSize,
  formatDuration,
} from '../lib/utils'

describe('isValidLat', () => {
  it('returns true for valid latitudes', () => {
    expect(isValidLat(0)).toBe(true)
    expect(isValidLat(90)).toBe(true)
    expect(isValidLat(-90)).toBe(true)
    expect(isValidLat(39.9087)).toBe(true)
  })
  it('returns false for invalid latitudes', () => {
    expect(isValidLat(91)).toBe(false)
    expect(isValidLat(-91)).toBe(false)
    expect(isValidLat(NaN)).toBe(false)
  })
})

describe('isValidLon', () => {
  it('returns true for valid longitudes', () => {
    expect(isValidLon(0)).toBe(true)
    expect(isValidLon(180)).toBe(true)
    expect(isValidLon(-180)).toBe(true)
    expect(isValidLon(116.3975)).toBe(true)
  })
  it('returns false for invalid longitudes', () => {
    expect(isValidLon(181)).toBe(false)
    expect(isValidLon(-181)).toBe(false)
    expect(isValidLon(NaN)).toBe(false)
  })
})

describe('parseCoordinate', () => {
  it('parses valid strings', () => {
    expect(parseCoordinate('39.9087')).toBe(39.9087)
    expect(parseCoordinate('-116.3975')).toBe(-116.3975)
    expect(parseCoordinate('  0  ')).toBe(0)
  })
  it('returns null for invalid strings', () => {
    expect(parseCoordinate('')).toBeNull()
    expect(parseCoordinate('abc')).toBeNull()
    expect(parseCoordinate('   ')).toBeNull()
  })
})

describe('validateFile', () => {
  it('returns null for valid CSV file', () => {
    const file = new File(['a,b,c'], 'test.csv', { type: 'text/csv' })
    expect(validateFile(file)).toBeNull()
  })
  it('returns error for unsupported type', () => {
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })
    expect(validateFile(file)).toContain('不支持')
  })
  it('returns error for empty file', () => {
    const file = new File([], 'empty.csv', { type: 'text/csv' })
    expect(validateFile(file)).toContain('为空')
  })
})

describe('formatCoords', () => {
  it('formats lat and lon', () => {
    expect(formatCoords(39.9087, 116.3975)).toBe('39.908700, 116.397500')
    expect(formatCoords(39.9087, 116.3975, 2)).toBe('39.91, 116.40')
  })
})

describe('formatFileSize', () => {
  it('formats B, KB, MB', () => {
    expect(formatFileSize(500)).toBe('500 B')
    expect(formatFileSize(1500)).toBe('1.5 KB')
    expect(formatFileSize(1500000)).toBe('1.4 MB')
  })
})

describe('formatDuration', () => {
  it('formats seconds and minutes', () => {
    expect(formatDuration(30)).toBe('30 秒')
    expect(formatDuration(90)).toBe('2 分钟')
    expect(formatDuration(3600)).toBe('1.0 小时')
  })
  it('handles edge cases', () => {
    expect(formatDuration(-1)).toBe('计算中...')
    expect(formatDuration(Infinity)).toBe('计算中...')
  })
})
