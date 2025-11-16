import React from 'react'

/**
 * Simple markdown parser for chat messages
 * Converts markdown to HTML/React elements
 */

/**
 * Parse markdown text and return JSX elements
 */
export const parseMarkdown = (text) => {
  if (!text || typeof text !== 'string') return text

  // Split by lines to handle different markdown elements
  const lines = text.split('\n')
  const elements = []
  let currentList = null

  lines.forEach((line, index) => {
    const trimmedLine = line.trim()

    // Handle headers (## Header or **Header**)
    if (trimmedLine.startsWith('##')) {
      const headerText = trimmedLine.replace(/^##+\s*/, '')
      elements.push(
        React.createElement('h3', { key: `header-${index}`, className: 'font-bold text-lg mt-4 mb-2' }, 
          parseInlineMarkdown(headerText)
        )
      )
      return
    }

    // Handle bullet points (* item or - item) - can have multiple spaces after *
    // Also remove "bullet" text if it appears at the start (case-insensitive)
    if (trimmedLine.match(/^[\*\-\•]\s+/) || trimmedLine.toLowerCase().startsWith('bullet')) {
      let listItem = trimmedLine.replace(/^[\*\-\•]\s+/, '').trim()
      // Remove "bullet" text if present (case-insensitive, with optional colon)
      listItem = listItem.replace(/^bullet\s*:?\s*/i, '').trim()
      if (!currentList) {
        currentList = []
      }
      currentList.push(
        React.createElement('li', { key: `list-${index}`, className: 'ml-4 mb-1.5' }, 
          parseInlineMarkdown(listItem)
        )
      )
      return
    }

    // Handle nested bullet points (indented with 4+ spaces)
    if (trimmedLine.match(/^\s{4,}[\*\-\•]\s+/)) {
      const listItem = trimmedLine.replace(/^\s+[\*\-\•]\s+/, '').trim()
      if (!currentList) {
        currentList = []
      }
      currentList.push(
        React.createElement('li', { key: `list-nested-${index}`, className: 'ml-8 mb-1.5 list-disc' }, 
          parseInlineMarkdown(listItem)
        )
      )
      return
    }

    // If we have a list and hit a non-list line, close the list
    if (currentList && currentList.length > 0) {
      elements.push(
        React.createElement('ul', { key: `ul-${index}`, className: 'list-disc mb-3 space-y-1.5 pl-5' }, 
          currentList
        )
      )
      currentList = null
    }

    // Handle regular paragraphs
    if (trimmedLine) {
      elements.push(
        React.createElement('p', { key: `p-${index}`, className: 'mb-2' }, 
          parseInlineMarkdown(trimmedLine)
        )
      )
    } else if (index < lines.length - 1) {
      // Empty line - add spacing
      elements.push(React.createElement('br', { key: `br-${index}` }))
    }
  })

  // Close any remaining list
  if (currentList && currentList.length > 0) {
    elements.push(
      React.createElement('ul', { key: 'ul-final', className: 'list-disc mb-3 space-y-1.5 pl-5' }, 
        currentList
      )
    )
  }

  return elements.length > 0 ? elements : parseInlineMarkdown(text)
}

/**
 * Parse inline markdown (bold, italic, etc.)
 */
export const parseInlineMarkdown = (text) => {
  if (!text || typeof text !== 'string') return text

  const parts = []
  let currentIndex = 0
  let key = 0

  // Match **bold** (must be double asterisks, not single)
  // Priority: **bold** first, then *italic*, then `code`
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let match
  const matches = []
  
  // Collect all matches first
  while ((match = regex.exec(text)) !== null) {
    matches.push({
      index: match.index,
      text: match[0],
      length: match[0].length
    })
  }

  // Process matches
  matches.forEach((match) => {
    // Add text before the match
    if (match.index > currentIndex) {
      const beforeText = text.substring(currentIndex, match.index)
      if (beforeText) {
        parts.push(beforeText)
      }
    }

    const matchedText = match.text

    // Handle **bold** (double asterisks)
    if (matchedText.startsWith('**') && matchedText.endsWith('**') && matchedText.length > 4) {
      const boldText = matchedText.slice(2, -2)
      parts.push(
        React.createElement('strong', { key: `bold-${key++}`, className: 'font-semibold' }, boldText)
      )
    }
    // Handle *italic* (single asterisk, but not if it's part of **bold**)
    else if (matchedText.startsWith('*') && matchedText.endsWith('*') && !matchedText.startsWith('**')) {
      const italicText = matchedText.slice(1, -1)
      parts.push(
        React.createElement('em', { key: `italic-${key++}`, className: 'italic' }, italicText)
      )
    }
    // Handle `code`
    else if (matchedText.startsWith('`') && matchedText.endsWith('`')) {
      const codeText = matchedText.slice(1, -1)
      parts.push(
        React.createElement('code', { key: `code-${key++}`, className: 'bg-gray-200 px-1 rounded text-sm font-mono' }, codeText)
      )
    } else {
      // If no match, just add the text
      parts.push(matchedText)
    }

    currentIndex = match.index + match.length
  })

  // Add remaining text
  if (currentIndex < text.length) {
    const remainingText = text.substring(currentIndex)
    if (remainingText) {
      parts.push(remainingText)
    }
  }

  return parts.length > 0 ? parts : text
}

