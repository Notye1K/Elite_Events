export const APP_TIME_ZONE = "America/Sao_Paulo";

function calendarDateKey(value: Date) {
  const parts = new Intl.DateTimeFormat("pt-BR", {
    timeZone: APP_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";

  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function isEventFromPreviousDay(
  startsAt: string,
  now: Date = new Date(),
) {
  const eventDate = new Date(startsAt);
  if (Number.isNaN(eventDate.getTime())) return false;
  return calendarDateKey(eventDate) < calendarDateKey(now);
}
