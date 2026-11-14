"use client";

import { Loader2, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";

type Me = { role: string; email: string };
type Group = { id: string; name: string };
type Invite = {
  id: string;
  role: string;
  group_id: string | null;
  expires_at: string;
  max_uses: number;
  use_count: number;
  revoked_at: string | null;
};
type Workspace = {
  id: string;
  name: string;
  logo_url: string | null;
  accent_color: string;
  allowed_domains: string[];
};
type Analytics = {
  documents: number;
  failed_documents: number;
  storage_bytes: number;
  conversations: number;
  answers: number;
  refusals: number;
  unanswered_open: number;
  unanswered_resolved: number;
};
type Gap = { id: string; question: string; reason: string; created_at: string };
type Member = {
  user_id: string;
  email: string | null;
  role: string;
  group_id: string | null;
  status: string;
};

const ROLES = ["guest", "employee", "engineering", "security", "hr", "finance", "admin"];

export default function SettingsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [logo, setLogo] = useState("");
  const [accent, setAccent] = useState("#2563eb");
  const [domains, setDomains] = useState("");
  const [wsName, setWsName] = useState("");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [role, setRole] = useState("employee");
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    supabaseBrowser()
      .auth.getSession()
      .then(({ data }) => setToken(data.session?.access_token ?? null));
  }, []);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [profile, groupData, memberData, inviteData] = await Promise.all([
        apiFetch<Me>("/me", token),
        apiFetch<{ groups: Group[] }>("/admin/groups", token),
        apiFetch<{ members: Member[] }>("/admin/members", token),
        apiFetch<{ invites: Invite[] }>("/admin/invites", token),
      ]);
      setMe(profile);
      setGroups(groupData.groups ?? []);
      setMembers(memberData.members ?? []);
      setInvites(inviteData.invites ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load settings");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    Promise.all([
      apiFetch<Me>("/me", token),
      apiFetch<{ groups: Group[] }>("/admin/groups", token),
      apiFetch<{ members: Member[] }>("/admin/members", token),
      apiFetch<{ invites: Invite[] }>("/admin/invites", token),
      apiFetch<Gap[]>("/admin/unanswered", token).then((d) => (d as unknown as { questions: Gap[] }).questions ?? []),
      apiFetch<Workspace>("/workspace/settings", token),
      apiFetch<Analytics>("/admin/analytics", token),
    ])
      .then(([profile, groupData, memberData, inviteData, gapData, ws, stats]) => {
        if (!active) return;
        setMe(profile);
        setGroups(groupData.groups ?? []);
        setMembers(memberData.members ?? []);
        setInvites(inviteData.invites ?? []);
        setGaps(gapData ?? []);
        setWorkspace(ws);
        setWsName(ws.name);
        setLogo(ws.logo_url ?? "");
        setAccent(ws.accent_color);
        setDomains(ws.allowed_domains.join(", "));
        setAnalytics(stats);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Could not load settings");
      });
    return () => {
      active = false;
    };
  }, [token, load]);

  async function saveWorkspace(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/workspace/settings", token, {
        method: "PATCH",
        body: JSON.stringify({
          name: wsName,
          logo_url: logo || null,
          accent_color: accent,
          allowed_domains: domains.split(/[\s,]+/).filter(Boolean),
        }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save settings");
    } finally {
      setBusy(false);
    }
  }

  async function downloadAudit() {
    if (!token) return;
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://enterprise-knowledge-copilot-2u57.onrender.com"}/audit/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "audit-log.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function gapAction(id: string, action: "resolve" | "delete") {
    if (!token) return;
    await apiFetch(
      action === "resolve" ? `/admin/unanswered/${id}/resolve` : `/admin/unanswered/${id}`,
      token,
      { method: action === "resolve" ? "POST" : "DELETE" },
    );
    await load();
  }

  async function createGroup(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !groupName.trim()) return;
    setBusy(true);
    try {
      await apiFetch("/admin/groups", token, {
        method: "POST",
        body: JSON.stringify({ name: groupName }),
      });
      setGroupName("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the group");
    } finally {
      setBusy(false);
    }
  }

  async function createInvite(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const data = await apiFetch<{ path: string }>("/admin/invites", token, {
        method: "POST",
        body: JSON.stringify({
          role,
          group_id: groupId || null,
          max_uses: 1,
          expires_hours: 72,
        }),
      });
      setInviteLink(`${window.location.origin}${data.path}`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the invite");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    if (!token) return;
    await apiFetch(`/admin/invites/${id}`, token, { method: "DELETE" });
    await load();
  }

  async function toggleMember(member: Member) {
    if (!token) return;
    const status = member.status === "active" ? "deactivated" : "active";
    await apiFetch(`/admin/members/${member.user_id}`, token, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    await load();
  }

  async function changeRole(member: Member, next: string) {
    if (!token) return;
    await apiFetch(`/admin/members/${member.user_id}`, token, {
      method: "PATCH",
      body: JSON.stringify({ role: next }),
    });
    await load();
  }

  if (!token) {
    return <p className="mx-auto max-w-2xl px-4 py-20 text-sm">Sign in to manage the workspace.</p>;
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-10">
      <header>
        <p className="mono text-[11px] uppercase tracking-[0.16em] text-[var(--text-muted)]">
          Workspace settings
        </p>
        <h1 className="mt-2 text-2xl font-semibold">{me ? me.email : "Loading…"}</h1>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Role: {me?.role ?? "…"}. Only owners can invite an admin, change an admin or remove
          ownership.
        </p>
      </header>

      {error ? (
        <p className="rounded-lg border border-[var(--danger)] px-3 py-2 text-xs text-[var(--danger)]">
          {error}
        </p>
      ) : null}

      <section className="panel p-5">
        <h2 className="text-sm font-semibold">Workspace settings</h2>
        <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={saveWorkspace}>
          <label className="text-xs">
            Name
            <input aria-label="Workspace name" className="input mt-1" onChange={(e) => setWsName(e.target.value)} value={wsName} />
          </label>
          <label className="text-xs">
            Logo URL
            <input aria-label="Logo URL" className="input mt-1" onChange={(e) => setLogo(e.target.value)} value={logo} />
          </label>
          <label className="text-xs">
            Accent colour
            <input aria-label="Accent colour" className="input mt-1" onChange={(e) => setAccent(e.target.value)} value={accent} />
          </label>
          <label className="text-xs">
            Allowed email domains
            <input aria-label="Allowed email domains" className="input mt-1" onChange={(e) => setDomains(e.target.value)} placeholder="company.com, example.org" value={domains} />
          </label>
          <button className="btn btn-primary" disabled={busy} type="submit">Save settings</button>
        </form>
        <p className="mt-2 text-xs text-[var(--text-muted)]">Current: {workspace?.name ?? "…"}</p>
      </section>

      <section className="panel p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Analytics</h2>
          <button className="btn" onClick={downloadAudit} type="button">Download audit CSV</button>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
          {analytics
            ? Object.entries(analytics).map(([key, value]) => (
                <div key={key} className="panel-2 p-3">
                  <dt className="text-[var(--text-muted)]">{key.replaceAll("_", " ")}</dt>
                  <dd className="mt-1 text-lg font-semibold">{String(value)}</dd>
                </div>
              ))
            : null}
        </dl>
      </section>

      <section className="panel p-5">
        <h2 className="text-sm font-semibold">Unanswered questions</h2>
        <ul className="mt-3 divide-y divide-[var(--border)] text-xs">
          {gaps.length === 0 ? <li className="py-2 text-[var(--text-muted)]">Queue is empty.</li> : null}
          {gaps.map((gap) => (
            <li className="flex flex-wrap items-center gap-2 py-2" key={gap.id}>
              <span className="min-w-48 flex-1">{gap.question}</span>
              <button className="underline decoration-dotted" onClick={() => gapAction(gap.id, "resolve")}>Resolve</button>
              <button className="text-[var(--danger)] underline decoration-dotted" onClick={() => gapAction(gap.id, "delete")}>Delete</button>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel p-5">
        <h2 className="text-sm font-semibold">Groups</h2>
        <form className="mt-3 flex gap-2" onSubmit={createGroup}>
          <input
            aria-label="Group name"
            className="input"
            onChange={(event) => setGroupName(event.target.value)}
            placeholder="Finance"
            value={groupName}
          />
          <button className="btn" disabled={busy} type="submit">
            Add group
          </button>
        </form>
        <p className="mt-3 text-xs text-[var(--text-muted)]">
          {groups.length ? groups.map((group) => group.name).join(" · ") : "No groups yet."}
        </p>
      </section>

      <section className="panel p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <UserPlus size={15} /> Invite someone
        </h2>
        <form className="mt-3 grid gap-2 sm:grid-cols-3" onSubmit={createInvite}>
          <select
            aria-label="Invite role"
            className="input"
            onChange={(event) => setRole(event.target.value)}
            value={role}
          >
            {ROLES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <select
            aria-label="Invite group"
            className="input"
            onChange={(event) => setGroupId(event.target.value)}
            value={groupId}
          >
            <option value="">No group</option>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
          <button className="btn btn-primary" disabled={busy} type="submit">
            {busy ? <Loader2 className="animate-spin" size={15} /> : null} Create link
          </button>
        </form>
        {inviteLink ? (
          <div className="mt-3 flex gap-2">
            <input aria-label="Invite link" className="input" readOnly value={inviteLink} />
            <button
              className="btn"
              onClick={() => navigator.clipboard.writeText(inviteLink)}
              type="button"
            >
              Copy
            </button>
          </div>
        ) : null}
        <ul className="mt-4 divide-y divide-[var(--border)] text-xs">
          {invites.map((invite) => (
            <li className="flex items-center justify-between gap-2 py-2" key={invite.id}>
              <span>
                {invite.role}
                {invite.group_id ? " · group" : ""} · {invite.use_count}/{invite.max_uses} used
                {invite.revoked_at ? " · revoked" : ""}
              </span>
              {!invite.revoked_at ? (
                <button className="underline decoration-dotted" onClick={() => revoke(invite.id)}>
                  Revoke
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel p-5">
        <h2 className="text-sm font-semibold">Members</h2>
        <ul className="mt-3 divide-y divide-[var(--border)] text-xs">
          {members.map((member) => (
            <li className="flex flex-wrap items-center gap-2 py-3" key={member.user_id}>
              <span className="min-w-40 flex-1">{member.email ?? member.user_id}</span>
              {member.role === "owner" ? (
                <span className="chip text-[10px]">owner</span>
              ) : (
                <select
                  aria-label={`Role for ${member.email ?? member.user_id}`}
                  className="input w-32"
                  onChange={(event) => changeRole(member, event.target.value)}
                  value={member.role}
                >
                  {ROLES.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              )}
              <span className="text-[var(--text-muted)]">{member.status}</span>
              {member.role !== "owner" ? (
                <button className="underline decoration-dotted" onClick={() => toggleMember(member)}>
                  {member.status === "active" ? "Deactivate" : "Reactivate"}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
