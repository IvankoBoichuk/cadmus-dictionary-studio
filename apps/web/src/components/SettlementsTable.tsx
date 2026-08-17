import type { SettlementMappingResponse } from "../api";

const STATUS_LABELS: Record<SettlementMappingResponse["status"], string> = {
  unresolved: "не зіставлено",
  suggested: "запропоновано",
  confirmed: "підтверджено",
};

const STATUS_BADGE_CLASS: Record<SettlementMappingResponse["status"], string> = {
  unresolved: "badge--unresolved",
  suggested: "badge--suggested",
  confirmed: "badge--confirmed",
};

export function SettlementsTable({
  mappings,
  onEdit,
  onDelete,
  onConfirm,
  onUnconfirm,
  deleteState,
}: {
  mappings: SettlementMappingResponse[];
  onEdit: (item: SettlementMappingResponse) => void;
  onDelete: (item: SettlementMappingResponse) => void;
  onConfirm: (item: SettlementMappingResponse) => void;
  onUnconfirm: (item: SettlementMappingResponse) => void;
  deleteState: Record<string, { pending: boolean; error: string | undefined } | undefined>;
}) {
  if (mappings.length === 0) {
    return <p className="lede">Географічних міток ще немає. Додайте першу нижче.</p>;
  }

  return (
    <div className="table-wrapper">
      <table className="settlement-table">
        <caption className="visually-hidden">
          Список географічних міток словника
        </caption>
        <thead>
          <tr>
            <th scope="col">Позначка з оригіналу</th>
            <th scope="col">Сучасна відповідність</th>
            <th scope="col">Громада</th>
            <th scope="col">Статус</th>
            <th scope="col">Дії</th>
          </tr>
        </thead>
        <tbody>
          {mappings.map((item) => {
            const rowDeleteState = deleteState[item.id];
            return (
              <tr key={item.id}>
                <td>{item.source_label}</td>
                <td>{item.modern_settlement_name ?? "—"}</td>
                <td>{item.community_name ?? "—"}</td>
                <td>
                  <span className={`badge ${STATUS_BADGE_CLASS[item.status]}`}>
                    {STATUS_LABELS[item.status]}
                  </span>
                </td>
                <td>
                  <div className="table-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onEdit(item)}
                    >
                      Редагувати
                    </button>
                    {item.status === "suggested" && (
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => onConfirm(item)}
                      >
                        Підтвердити
                      </button>
                    )}
                    {item.status === "confirmed" && (
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => onUnconfirm(item)}
                      >
                        Скасувати підтвердження
                      </button>
                    )}
                    <button
                      type="button"
                      className="danger-button"
                      disabled={rowDeleteState?.pending}
                      onClick={() => onDelete(item)}
                    >
                      {rowDeleteState?.pending ? "Видаляємо…" : "Видалити"}
                    </button>
                  </div>
                  {rowDeleteState?.error && (
                    <p className="field-error" role="alert">
                      {rowDeleteState.error}
                    </p>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
