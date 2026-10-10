export type UserRole = "administrator" | "analyst" | "reviewer" | "viewer";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  active: boolean;
}

export const PAGE_PERMISSIONS: Record<string, UserRole[]> = {
  "/": ["administrator", "analyst", "reviewer", "viewer"],
  "/map": ["administrator", "analyst", "reviewer", "viewer"],
  "/properties": ["administrator", "analyst", "reviewer", "viewer"],
  "/analytics": ["administrator", "analyst", "viewer"],
  "/history": ["administrator", "analyst"],
  "/challenge-queries": ["administrator", "analyst"],
  "/review": ["administrator", "reviewer"],
  "/settings": ["administrator"],
  "/admin/users": ["administrator"],
};

export const DEFAULT_ROUTE: Record<UserRole, string> = {
  administrator: "/", analyst: "/", reviewer: "/", viewer: "/",
};

export function canVisit(role: UserRole, path: string): boolean {
  return PAGE_PERMISSIONS[path]?.includes(role) ?? false;
}

export function roleLabel(role: UserRole): string {
  if (role === "analyst") return "Urban Analyst";
  return role[0].toUpperCase() + role.slice(1);
}
