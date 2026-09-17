import { useEffect, useRef, useState } from 'react'

const TOP_REVEAL_OFFSET = 24
const HIDE_OFFSET = 72
const DIRECTION_DELTA = 7

function scrollPosition(target) {
  return target === window ? window.scrollY : target.scrollTop
}

export function useSmartHeader({ scrollContainerRef, routeKey, locked = false } = {}) {
  const [visible, setVisible] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const lastPosition = useRef(0)

  useEffect(() => {
    const handleModalVisibility = event => setModalOpen(Boolean(event.detail?.open))
    window.addEventListener('fdas:modal-visibility', handleModalVisibility)
    return () => window.removeEventListener('fdas:modal-visibility', handleModalVisibility)
  }, [])

  useEffect(() => {
    const target = scrollContainerRef?.current || window
    lastPosition.current = scrollPosition(target)
    setVisible(true)

    if (locked || modalOpen) return undefined

    let animationFrame = null
    const handleScroll = () => {
      if (animationFrame !== null) return
      animationFrame = window.requestAnimationFrame(() => {
        const currentPosition = Math.max(0, scrollPosition(target))
        const delta = currentPosition - lastPosition.current

        if (currentPosition <= TOP_REVEAL_OFFSET) {
          setVisible(true)
        } else if (Math.abs(delta) >= DIRECTION_DELTA) {
          if (delta > 0 && currentPosition >= HIDE_OFFSET) setVisible(false)
          if (delta < 0) setVisible(true)
          lastPosition.current = currentPosition
        }
        animationFrame = null
      })
    }

    target.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      target.removeEventListener('scroll', handleScroll)
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame)
    }
  }, [locked, modalOpen, routeKey, scrollContainerRef])

  return visible
}
