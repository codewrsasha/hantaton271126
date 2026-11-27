import { ModulePage } from '../../shared/ModulePage'
import type { Report } from '../../shared/contracts'

export default function ReportsPage() {
  return (
    <ModulePage<Report[]>
      title="Отчёты"
      description="Отчёты о несоответствиях с цитатами и ссылками на источники."
      path="/reports"
      emptyTitle="Отчётов пока нет"
      emptyDescription="Отчёты можно будет сформировать по результатам проверки."
    >
      {(reports) => reports.length ? <ul className="resource-list">{reports.map((report) =>
        <li key={report.id}>{report.filename}</li>)}</ul> : null}
    </ModulePage>
  )
}
