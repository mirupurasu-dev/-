export default function SettingsPage() {
  return (
    <div className="px-4 pt-6 safe-top">
      <header className="mb-5">
        <div className="text-[11px] text-muted-fg">Settings</div>
        <h1 className="text-2xl font-bold tracking-tight">設定</h1>
      </header>
      <ul className="space-y-2">
        <SettingItem label="API エンドポイント" value={process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000'} />
        <SettingItem label="分数ケリー係数" value="0.25 (1/4)" />
        <SettingItem label="EV 閾値" value="+10%" />
        <SettingItem label="掛け金上限" value="資金の 5%" />
      </ul>
    </div>
  );
}

function SettingItem({ label, value }: { label: string; value: string }) {
  return (
    <li className="rounded-xl bg-card border border-border p-3 flex items-center justify-between">
      <span className="text-sm">{label}</span>
      <span className="text-[11px] text-muted-fg tabular">{value}</span>
    </li>
  );
}
