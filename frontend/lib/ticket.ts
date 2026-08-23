const ticketStatusLabels: Record<string, string> = {
  valid: "Válido",
  used: "Utilizado",
  cancelled: "Cancelado",
};

export function ticketStatusLabel(status: string) {
  return ticketStatusLabels[status] ?? "Status desconhecido";
}
