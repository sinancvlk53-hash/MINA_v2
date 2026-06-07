import React from 'react'
import LogStream from './LogStream.jsx'

export default function LogPanel({ logs = [], testLogs = [] }) {
  return (
    <div className="panel panel-log">
      <LogStream logs={logs} testLogs={testLogs} />
    </div>
  )
}
