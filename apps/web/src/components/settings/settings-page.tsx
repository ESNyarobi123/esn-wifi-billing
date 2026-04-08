"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiGet, apiPost, apiPut } from "@/lib/api/client";
import type { SiteRow, SystemSettingRow } from "@/lib/api/types";

export function SettingsPage() {
  return (
    <Tabs defaultValue="sites">
      <TabsList>
        <TabsTrigger value="sites">Sites</TabsTrigger>
        <TabsTrigger value="branding">Portal branding</TabsTrigger>
        <TabsTrigger value="system">System settings</TabsTrigger>
      </TabsList>
      <TabsContent value="sites" className="mt-6">
        <SitesSection />
      </TabsContent>
      <TabsContent value="branding" className="mt-6">
        <BrandingSection />
      </TabsContent>
      <TabsContent value="system" className="mt-6">
        <SystemSettingsSection />
      </TabsContent>
    </Tabs>
  );
}

function SitesSection() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["sites"], queryFn: () => apiGet<SiteRow[]>("/sites") });
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [timezone, setTimezone] = useState("Africa/Dar_es_Salaam");
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await apiPost("/sites", { name, slug, timezone });
      toast.success("Site created");
      setName("");
      setSlug("");
      void qc.invalidateQueries({ queryKey: ["sites"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  if (q.isLoading) return <QueryLoading rows={3} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">Sites</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Slug</TableHead>
                <TableHead>Timezone</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {q.data?.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>{s.name}</TableCell>
                  <TableCell className="font-mono text-xs">{s.slug}</TableCell>
                  <TableCell className="text-sm">{s.timezone}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">New site</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={create}>
            <div className="space-y-1">
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="space-y-1">
              <SlugField slug={slug} onChange={setSlug} />
            </div>
            <div className="space-y-1">
              <Label>Timezone</Label>
              <Input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
            </div>
            <Button type="submit" disabled={busy}>
              {busy ? "Creating…" : "Create site"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function SlugField({ slug, onChange }: { slug: string; onChange: (s: string) => void }) {
  return (
    <div className="space-y-1">
      <Label>Slug (lowercase, hyphens)</Label>
      <Input value={slug} onChange={(e) => onChange(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))} required />
    </div>
  );
}

function BrandingSection() {
  const qc = useQueryClient();
  const sitesQ = useQuery({ queryKey: ["sites"], queryFn: () => apiGet<SiteRow[]>("/sites") });
  const [siteId, setSiteId] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [primary, setPrimary] = useState("#FBA002");
  const [welcome, setWelcome] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!siteId && sitesQ.data?.length) setSiteId(sitesQ.data[0].id);
  }, [siteId, sitesQ.data]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!siteId) return;
    setBusy(true);
    try {
      await apiPut(`/sites/${siteId}/portal-branding`, {
        logo_url: logoUrl || null,
        primary_color: primary || null,
        welcome_message: welcome || null,
        support_phone: phone || null,
      });
      toast.success("Branding saved");
      void qc.invalidateQueries({ queryKey: ["sites"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle className="font-display text-lg">Captive portal branding</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-3" onSubmit={save}>
          <div className="space-y-1">
            <Label>Site</Label>
            <select className="flex h-10 w-full rounded-md border border-input bg-card px-3 text-sm" value={siteId} onChange={(e) => setSiteId(e.target.value)}>
              {sitesQ.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.slug})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Logo URL</Label>
            <Input value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} placeholder="https://…" />
          </div>
          <div className="space-y-1">
            <Label>Primary color</Label>
            <Input value={primary} onChange={(e) => setPrimary(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Welcome message</Label>
            <Input value={welcome} onChange={(e) => setWelcome(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Support phone</Label>
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <Button type="submit" disabled={busy || !siteId}>
            {busy ? "Saving…" : "Save branding"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function SystemSettingsSection() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: () => apiGet<SystemSettingRow[]>("/settings") });
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [jsonText, setJsonText] = useState("{}");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!q.data?.length) return;
    const row = q.data.find((r) => r.key === selectedKey) ?? q.data[0];
    if (!row) return;
    if (selectedKey === null) setSelectedKey(row.key);
    setJsonText(JSON.stringify(row.value ?? {}, null, 2));
  }, [q.data, selectedKey]);

  async function saveSetting(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedKey) return;
    setBusy(true);
    try {
      const value = JSON.parse(jsonText) as Record<string, unknown>;
      await apiPut("/settings", { key: selectedKey, value });
      toast.success("Setting saved");
      void qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Invalid JSON or request failed");
    } finally {
      setBusy(false);
    }
  }

  if (q.isLoading) return <QueryLoading rows={2} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  const row = q.data?.find((r) => r.key === selectedKey);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Keys</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {q.data?.map((r) => (
            <Button
              key={r.key}
              variant={r.key === selectedKey ? "default" : "outline"}
              className="w-full justify-start font-mono text-xs"
              type="button"
              onClick={() => {
                setSelectedKey(r.key);
                setJsonText(JSON.stringify(r.value ?? {}, null, 2));
              }}
            >
              {r.key}
            </Button>
          ))}
          {!q.data?.length && <p className="text-sm text-muted-foreground">No system settings rows.</p>}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Value (JSON)</CardTitle>
          {row?.description && <p className="text-sm text-muted-foreground">{row.description}</p>}
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={saveSetting}>
            <textarea
              className="min-h-[240px] w-full rounded-md border border-input bg-card p-3 font-mono text-xs"
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
            />
            <Button type="submit" disabled={busy || !selectedKey}>
              {busy ? "Saving…" : "Save"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
