import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import type { ChartConfig } from '../types'

// Light professional palette
const ACCENT = '#0284c7' // sky-600
const SECOND = '#7c3aed' // violet-600
const GRID = '#e2e8f0'
const AXIS = '#64748b'

const tooltipStyle = {
  backgroundColor: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: 12,
  fontSize: 12,
  color: '#1e293b',
  boxShadow: '0 4px 16px rgba(15,23,42,0.08)',
}

export default function ChartRenderer({ chart }: { chart: ChartConfig }) {
  const data = chart.data ?? []

  if (chart.type === 'line') {
    const groups = chart.group
      ? Array.from(new Set(data.map((d) => String(d[chart.group!]))))
      : null
    return (
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey={chart.x} stroke={AXIS} fontSize={11} tickLine={false} />
          <YAxis stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          {groups && <Legend />}
          {(groups ?? [null]).map((g, i) => (
            <Line
              key={g ?? 'series'}
              type="monotone"
              dataKey={chart.y}
              data={groups ? data.filter((d) => String(d[chart.group!]) === g) : data}
              name={g ?? chart.y}
              stroke={i % 2 ? SECOND : ACCENT}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (chart.type === 'bar') {
    const key = chart.x === 'name' ? 'name' : chart.x
    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          layout={chart.horizontal ? 'vertical' : 'horizontal'}
          margin={{ top: 8, right: 16, bottom: 4, left: chart.horizontal ? 40 : 0 }}
        >
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          {chart.horizontal ? (
            <>
              <XAxis type="number" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis dataKey={key} type="category" stroke={AXIS} fontSize={11} width={110} tickLine={false} />
            </>
          ) : (
            <>
              <XAxis dataKey={key} stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
            </>
          )}
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey={chart.y} fill={ACCENT} radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (chart.type === 'scatter') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey={chart.x} name={chart.x} stroke={AXIS} fontSize={11} tickLine={false} />
          <YAxis dataKey={chart.y} name={chart.y} stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
          <ZAxis range={[40, 40]} />
          <Tooltip contentStyle={tooltipStyle} />
          <Scatter data={data} fill={ACCENT} fillOpacity={0.65} />
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  // table fallback
  const cols = chart.columns ?? Object.keys(data[0] ?? {})
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-slate-500">
            {cols.map((c) => (
              <th key={c} className="border-b border-slate-200 px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="text-slate-700">
              {cols.map((c) => (
                <td key={c} className="border-b border-slate-100 px-3 py-1.5">
                  {String(row[c] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
