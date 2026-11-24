import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Check, SlidersHorizontal, X } from 'lucide-react'
import { tagIcon, tagLabel } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { useTags } from '../../hooks/useTags'
import { useTopicPreferences } from '../../hooks/useTopicPreferences'
import { exploreFilter } from '../../utils/explore'
import type { ExploreFilter } from '../../utils/explore'
import { orderByPreference } from '../../utils/tags'
import styles from './ExploreFilters.module.css'

type Props = {
  active: ExploreFilter
  onChange: (filter: ExploreFilter) => void
}

/*
 * "All", then a "Filter" button that opens a panel to pick several tags,
 * then the picked tags as chips (click one to remove it). The row scrolls
 * sideways on narrow screens instead of wrapping. Changes apply straight away.
 */
export function ExploreFilters({ active, onChange }: Props) {
  const { t } = useStrings()
  const { status, tags, retry } = useTags()
  const { preferences } = useTopicPreferences()
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const selected = new Set(active.tagIds)
  const count = active.tagIds.length
  // Picked tags in the same order as the panel; IDs the database doesn't know are left out.
  const ordered = orderByPreference(tags, preferences)
  const selectedTags = ordered.filter((tag) => selected.has(tag.id))

  // Only the tags change; a search in the search bar stays and looks inside the new selection.
  const setTags = (tagIds: string[]) => onChange(exploreFilter(tagIds))
  const toggle = (id: string) =>
    setTags(
      selected.has(id)
        ? active.tagIds.filter((tagId) => tagId !== id)
        : [...active.tagIds, id],
    )

  // Clicking outside the bar closes the panel.
  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const close = () => {
    setOpen(false)
    buttonRef.current?.focus()
  }

  const onPanelKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.stopPropagation()
      close()
    }
  }

  return (
    <div ref={rootRef} className={styles.bar}>
      <div
        className={styles.row}
        role="group"
        aria-label={t.explore.filtersLabel}
      >
        <button
          type="button"
          className={styles.chip}
          aria-pressed={count === 0}
          onClick={() => setTags([])}
        >
          {t.explore.all}
        </button>
        <button
          ref={buttonRef}
          type="button"
          className={`${styles.chip} ${styles.filterButton}`}
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={count ? t.explore.filterCount(count) : undefined}
          onClick={() => setOpen((value) => !value)}
        >
          <SlidersHorizontal size={16} aria-hidden="true" />
          {t.explore.filter}
          {count > 0 && (
            <span className={styles.count} aria-hidden="true">
              {count}
            </span>
          )}
        </button>
        {selectedTags.map((tag) => {
          const Icon = tagIcon(tag.name)
          const label = tagLabel(tag.name, t)
          return (
            <button
              key={tag.id}
              type="button"
              className={`${styles.chip} ${styles.selected}`}
              aria-label={t.explore.removeTag(label)}
              onClick={() => toggle(tag.id)}
            >
              <Icon size={16} aria-hidden="true" />
              {label}
              <X size={14} aria-hidden="true" />
            </button>
          )
        })}
      </div>

      {open && (
        <div id={panelId} className={styles.panel} onKeyDown={onPanelKeyDown}>
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>{t.explore.filterByTags}</legend>
            <p className={styles.hint}>{t.explore.filterHint}</p>
            {status === 'loading' && (
              <p role="status">{t.explore.tagsLoading}</p>
            )}
            {status === 'error' && (
              <p role="alert" className={styles.error}>
                {t.explore.tagsFailed}{' '}
                <button type="button" className={styles.link} onClick={retry}>
                  {t.explore.retry}
                </button>
              </p>
            )}
            {status === 'ready' && (
              <div className={styles.options}>
                {ordered.map((tag) => {
                  const Icon = tagIcon(tag.name)
                  const checked = selected.has(tag.id)
                  return (
                    <label key={tag.id} className={styles.option}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(tag.id)}
                      />
                      {checked ? (
                        <Check size={16} aria-hidden="true" />
                      ) : (
                        <Icon size={16} aria-hidden="true" />
                      )}
                      {tagLabel(tag.name, t)}
                    </label>
                  )
                })}
              </div>
            )}
          </fieldset>
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.link}
              onClick={() => setTags([])}
              disabled={count === 0}
            >
              {t.explore.clearFilters}
            </button>
            <button type="button" className={styles.done} onClick={close}>
              {t.explore.done}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
