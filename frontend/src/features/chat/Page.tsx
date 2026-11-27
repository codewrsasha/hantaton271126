import { MessagesSquare } from 'lucide-react'
import { ModulePage } from '../../shared/ModulePage'
import type { ChatStatus } from '../../shared/contracts'

export default function ChatPage() {
  return (
    <ModulePage<ChatStatus>
      title="ИИ-чат"
      description="Дополнительный модуль для уточнения результатов проверки."
      icon={MessagesSquare}
      path="/chat/status"
      emptyTitle="Чат пока недоступен"
      emptyDescription="Модуль появится после подключения локальной языковой модели."
    >
      {(status) => status.state === 'ready' ? <p className="empty-state">Локальный сервис чата доступен.</p> : null}
    </ModulePage>
  )
}
