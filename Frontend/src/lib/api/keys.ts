/**
 * TanStack Query keys. Each domain's `all` key is a prefix of its other keys, so
 * `invalidateQueries({ queryKey: keys.documents.all })` refreshes every documents query.
 */
type Filters = Record<string, string | number | boolean | null | undefined>;

export const keys = {
  users: {
    all: ["users"] as const,
    me: () => ["users", "me"] as const,
  },
  documents: {
    all: ["documents"] as const,
    list: (filters: Filters = {}) => ["documents", "list", filters] as const,
    detail: (id: string) => ["documents", "detail", id] as const,
  },
  conversations: {
    all: ["conversations"] as const,
    list: (filters: Filters = {}) => ["conversations", "list", filters] as const,
  },
  messages: {
    all: ["messages"] as const,
    list: (conversationId: string) => ["messages", conversationId] as const,
  },
  generations: {
    all: ["generations"] as const,
    list: (filters: Filters = {}) => ["generations", "list", filters] as const,
    detail: (id: string) => ["generations", "detail", id] as const,
  },
  admin: {
    all: ["admin"] as const,
    stats: () => ["admin", "stats"] as const,
    users: (filters: Filters = {}) => ["admin", "users", filters] as const,
    activity: (filters: Filters = {}) => ["admin", "activity", filters] as const,
  },
};
