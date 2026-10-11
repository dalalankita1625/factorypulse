// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('FactoryPulse dashboard',()=>{
  it('shows the dashboard title and synthetic data disclosure while loading',()=>{
    render(<App />)
    expect(screen.getByText('Operations overview')).toBeTruthy()
    expect(screen.getByText(/Synthetic sample data/)).toBeTruthy()
  })
})
