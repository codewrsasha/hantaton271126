import { ModulePage } from '../../shared/ModulePage'
import type { Report } from '../../shared/contracts'

export default function ReportsPage() {
  return (
    <ModulePage<Report[]>
      title="Отчёты"
      description="Материалы о несоответствиях с цитатами и реквизитами источников."
      path="/reports"
      sectionTitle="Сформированные отчёты"
      emptyTitle="Отчётов пока нет"
      emptyDescription="Отчёты можно будет сформировать по результатам проверки."
    >
      {(reports) => reports.length ? (
        <ul className="resource-list stagger-list">
          {reports.map((report) => (
            <li key={report.id} className="resource-row">
              <span className="entry-name">{report.filename}</span>
              <a className="text-action" href={`#analysis?run=${encodeURIComponent(report.analysis_id)}`}>К проверке</a>
            </li>
          ))}
        </ul>
      ) : null}
    </ModulePage>
  )
}
