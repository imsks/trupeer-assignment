import type { ReactNode } from "react";

interface Props {
  sidebar: ReactNode;
  player: ReactNode;
}

export default function Layout({ sidebar, player }: Props) {
  return (
    <div className="flex h-screen w-screen bg-gray-50">
      <aside className="w-[320px] shrink-0 h-full overflow-hidden">
        {sidebar}
      </aside>
      <main className="flex-1 h-full min-w-0">{player}</main>
    </div>
  );
}
