import { createContext, useContext, useRef, useCallback, type ReactNode } from 'react'

interface AudioManagerContextValue {
  /** Register an audio element and return a cleanup function. */
  play: (el: HTMLAudioElement) => () => void
}

const AudioManagerCtx = createContext<AudioManagerContextValue | null>(null)

export function useAudioManager() {
  const ctx = useContext(AudioManagerCtx)
  if (!ctx) throw new Error('useAudioManager must be used within AudioManagerProvider')
  return ctx
}

export function AudioManagerProvider({ children }: { children: ReactNode }) {
  const currentRef = useRef<HTMLAudioElement | null>(null)

  const play = useCallback((el: HTMLAudioElement): (() => void) => {
    // Stop whatever is currently playing
    if (currentRef.current && currentRef.current !== el) {
      currentRef.current.pause()
      currentRef.current.currentTime = 0
    }
    currentRef.current = el

    // Return a cleanup that clears the ref if this element is still current
    const captured = el
    return () => {
      if (currentRef.current === captured) {
        currentRef.current = null
      }
    }
  }, [])

  return (
    <AudioManagerCtx.Provider value={{ play }}>
      {children}
    </AudioManagerCtx.Provider>
  )
}
