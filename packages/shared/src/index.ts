export type AppConfig = {
  apiUrl: string;
  environment: "development" | "staging" | "production";
};

export function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}
