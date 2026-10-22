import type { Metadata } from "next";

import { MeetingsView } from "@/components/tools/tool-views";

export const metadata: Metadata = { title: "Meetings" };

export default function Page() {
  return <MeetingsView />;
}
