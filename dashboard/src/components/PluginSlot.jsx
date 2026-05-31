import React from 'react'

export default function PluginSlot({ id, label }) {
  return (
    <div className="plugin-slot">
      <span style={{ color: '#2d4a63', fontSize: 15, flexShrink: 0 }}>⬡</span>
      <div>
        <div className="plugin-slot-label">&lt;PluginSlot id="{id}"&gt;</div>
        <div className="plugin-slot-sub">{label}</div>
      </div>
    </div>
  )
}
