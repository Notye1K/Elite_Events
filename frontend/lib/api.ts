export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type SessionUser = {
  id: number;
  name: string;
  email: string;
  role: "client" | "organizer" | "gate";
};

const GENERIC_ERROR = "Ocorreu um erro inesperado. Tente novamente.";

const fieldLabels: Record<string, string> = {
  title: "Título",
  description: "Descrição",
  image_url: "Imagem (URL)",
  event_type: "Tipo de evento",
  starts_at: "Data/hora",
  location: "Local",
  capacity: "Capacidade",
  price_cents: "Preço",
  external_id: "ID externo",
  external_source: "Fonte externa",
  quantity: "Quantidade",
};

type ValidationErrorDetail = {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
  ctx?: Record<string, unknown>;
};

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function validationMessage(detail: ValidationErrorDetail) {
  switch (detail.type) {
    case "missing":
    case "string_too_short":
      return "é obrigatório";
    case "url_parsing":
    case "url_type":
      return "deve ser uma URL HTTP ou HTTPS válida";
    case "url_too_long":
    case "string_too_long":
      return `deve ter no máximo ${detail.ctx?.max_length ?? "o limite permitido de"} caracteres`;
    case "datetime_from_date_parsing":
    case "datetime_parsing":
      return "contém uma data ou hora inválida";
    case "greater_than":
      return `deve ser maior que ${detail.ctx?.gt ?? 0}`;
    case "greater_than_equal":
      return `deve ser maior ou igual a ${detail.ctx?.ge ?? 0}`;
    case "less_than_equal":
      return `deve ser menor ou igual a ${detail.ctx?.le ?? 0}`;
    case "value_error":
      return (detail.msg || "contém um valor inválido").replace(
        /^Value error,\s*/,
        "",
      );
    default:
      return "contém um valor inválido";
  }
}

function formatValidationErrors(details: ValidationErrorDetail[]) {
  return details
    .map((detail) => {
      const field = [...(detail.loc || [])]
        .reverse()
        .find((item) => typeof item === "string" && item !== "body");
      const label = typeof field === "string" ? fieldLabels[field] || field : "Campo";
      return `${label}: ${validationMessage(detail)}.`;
    })
    .join("\n");
}

function translateBackendMessage(detail: string) {
  const messages: Record<string, string> = {
    "Authentication required": "Faça login para continuar.",
    "Invalid token": "Sua sessão é inválida ou expirou. Entre novamente.",
    "User not found": "O usuário da sessão não foi encontrado.",
    "Insufficient role": "Seu perfil não tem permissão para realizar esta ação.",
    "Invalid ticket": "O ingresso é inválido ou foi adulterado.",
    "Ticket not found": "Ingresso não encontrado.",
  };

  if (messages[detail]) return messages[detail];
  if (detail.startsWith("External catalog error:")) {
    return "Não foi possível consultar o catálogo externo. Tente novamente.";
  }
  return detail;
}

function apiErrorMessage(data: unknown, status: number) {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string") return translateBackendMessage(detail);
    if (Array.isArray(detail)) {
      return formatValidationErrors(detail as ValidationErrorDetail[]);
    }
  }

  if (status >= 500) {
    return "O servidor encontrou um erro e não conseguiu concluir a operação. Tente novamente.";
  }
  return GENERIC_ERROR;
}

export function getErrorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : GENERIC_ERROR;
}

export function getToken() {
  return typeof window === "undefined" ? null : localStorage.getItem("token");
}
export function getUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem("user") || "null") as SessionUser | null;
  } catch {
    return null;
  }
}
export function saveSession(data: any) {
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("user", JSON.stringify(data.user));

  window.dispatchEvent(new Event("auth-changed"));
}
export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");

  window.dispatchEvent(new Event("auth-changed"));
}

export async function api(path: string, init: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.",
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(apiErrorMessage(data, response.status));
  return data;
}
