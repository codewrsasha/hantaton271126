import { FileChartColumn } from 'lucide-react'
import { ModulePage } from '../../shared/ModulePage'
import type { Report } from '../../shared/contracts'

export default function ReportsPage() {
  return (
    <ModulePage<Report[]>
      title="Отчёты"
      description="Отчёты о пробелах с цитатами и ссылками на источники."
      icon={FileChartColumn}
      path="/reports"
      emptyTitle="Отчётов пока нет"
      emptyDescription="Экспорт будет доступен после подключения результатов проверки."
    >
      {(reports) => reports.length ? <ul className="resource-list">{reports.map((report) =>
        <li key={report.id}>{report.filename}</li>)}</ul> : null}
    </ModulePage>
  )
}
