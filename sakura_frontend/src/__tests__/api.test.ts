import { describe, it, expect } from 'vitest'
import { getBaseUrl, getToken } from '../api'

describe('api', () => {
  it('getBaseUrl returns a URL string', () => {
    const url = getBaseUrl()
    expect(typeof url).toBe('string')
    expect(url).toMatch(/^https?:\/\/.+/)
  })

  it('getToken returns a string', () => {
    const token = getToken()
    expect(typeof token).toBe('string')
  })
})