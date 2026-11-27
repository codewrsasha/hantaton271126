import { useEffect, useRef } from 'react'

const integer = new Intl.NumberFormat('ru-RU')
const percent = new Intl.NumberFormat('ru-RU', { style: 'percent', maximumFractionDigits: 1 })

// Adapted from Magic UI Number Ticker (MIT). See DESIGN.md.
export function NumberTicker({ value, ratio = false }: { value: number; ratio?: boolean }) {
  const text = useRef<HTMLSpanElement>(null)
  const formatter = ratio ? percent : integer
  const finalValue = formatter.format(value)

  useEffect(() => {
    const element = text.current
    if (!element) return
    element.textContent = finalValue
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (!value || reducedMotion.matches) return

    let frame = 0
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      observer.disconnect()
      const start = performance.now()
      const tick = (now: number) => {
        const progress = reducedMotion.matches ? 1 : Math.min((now - start) / 420, 1)
        element.textContent = formatter.format(value * (1 - (1 - progress) ** 3))
        if (progress < 1) frame = requestAnimationFrame(tick)
      }
      frame = requestAnimationFrame(tick)
    })

    observer.observe(element)
    return () => {
      observer.disconnect()
      cancelAnimationFrame(frame)
    }
  }, [finalValue, formatter, value])

  return <><span className="sr-only">{finalValue}</span><span ref={text} aria-hidden="true">{finalValue}</span></>
}
