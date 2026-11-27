import { ModulePage } from '../../shared/ModulePage'
import type { ChatStatus } from '../../shared/contracts'

export default function ChatPage() {
  return (
    <ModulePage<ChatStatus>
      title="ИИ-чат"
      description="Вопросы по результатам проверки."
      path="/chat/status"
      sectionTitle="Состояние чата"
      emptyTitle="Чат пока недоступен"
      emptyDescription="Чат станет доступен после подключения локальной языковой модели."
    >
      {(status) => status.state === 'ready' ? <p className="module-state">Чат доступен.</p> : null}
    </ModulePage>
  )
}
