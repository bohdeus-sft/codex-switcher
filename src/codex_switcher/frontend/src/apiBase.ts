const DEFAULT_BACKEND = 'http://127.0.0.1:8765'
const BACKEND_PORT = '8765'

export function resolveApiBase(location: Pick<Location, 'hostname' | 'port' | 'protocol'>, configured?: string) {
  const explicit = configured?.trim()
  if (explicit) return explicit

  if (location.protocol === 'file:') {
    return DEFAULT_BACKEND
  }

  if (isLocalHost(location.hostname)) {
    return location.port === BACKEND_PORT ? '' : DEFAULT_BACKEND
  }

  return ''
}

function isLocalHost(hostname: string) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1' || hostname === '[::1]'
}
