"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Download, Loader2, WandSparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiDownload, apiPost } from "@/lib/api/client";
import { userFacingApiMessage } from "@/lib/api/error-utils";
import { getApiBaseUrl } from "@/lib/config";

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export function RouterProvisioningDownload({ routerId, routerName }: { routerId: string; routerName: string }) {
  const [open, setOpen] = useState(false);
  const [portalBaseUrl, setPortalBaseUrl] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [dnsName, setDnsName] = useState("");
  const [hotspotInterface, setHotspotInterface] = useState("bridge-hotspot");
  const [wanInterface, setWanInterface] = useState("ether1");
  const [lanCidr, setLanCidr] = useState("10.10.10.1/24");
  const [dhcpPoolStart, setDhcpPoolStart] = useState("10.10.10.10");
  const [dhcpPoolEnd, setDhcpPoolEnd] = useState("10.10.10.250");
  const [hotspotHtmlDirectory, setHotspotHtmlDirectory] = useState("");
  const [sslCertificateName, setSslCertificateName] = useState("");
  const [extraHosts, setExtraHosts] = useState("");
  const [providerTemplates, setProviderTemplates] = useState("clickpesa");
  const [autoDnsStatic, setAutoDnsStatic] = useState(true);
  const [autoIssueLetsEncrypt, setAutoIssueLetsEncrypt] = useState(false);

  useEffect(() => {
    setApiBaseUrl((current) => current || getApiBaseUrl());
    if (typeof window !== "undefined") {
      setPortalBaseUrl((current) => current || window.location.origin);
    }
  }, []);

  function buildBody() {
    const extraWalledGardenHosts = extraHosts
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const providers = providerTemplates
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    return {
      portal_base_url: portalBaseUrl.trim() || null,
      api_base_url: apiBaseUrl.trim() || null,
      dns_name: dnsName.trim() || null,
      hotspot_interface: hotspotInterface.trim(),
      wan_interface: wanInterface.trim(),
      lan_cidr: lanCidr.trim(),
      dhcp_pool_start: dhcpPoolStart.trim(),
      dhcp_pool_end: dhcpPoolEnd.trim(),
      hotspot_html_directory: hotspotHtmlDirectory.trim() || null,
      ssl_certificate_name: sslCertificateName.trim() || null,
      extra_walled_garden_hosts: extraWalledGardenHosts,
      provider_templates: providers,
      auto_dns_static: autoDnsStatic,
      auto_issue_letsencrypt: autoIssueLetsEncrypt,
    };
  }

  const downloadM = useMutation({
    mutationFn: async () => {
      return apiDownload(`/routers/${routerId}/provisioning-package`, {
        method: "POST",
        body: buildBody(),
      });
    },
    onSuccess: ({ blob, filename }) => {
      saveBlob(blob, filename || `esn-provisioning-${routerId}.zip`);
      toast.success("Provisioning package downloaded.");
      setOpen(false);
    },
    onError: (error: Error) => toast.error(userFacingApiMessage(error)),
  });

  const pushM = useMutation({
    mutationFn: async () => apiPost(`/routers/${routerId}/push-provisioning`, buildBody()),
    onSuccess: () => {
      toast.success("Provisioning package uploaded and imported on the router.");
      setOpen(false);
    },
    onError: (error: Error) => toast.error(userFacingApiMessage(error)),
  });

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <WandSparkles className="h-4 w-4" aria-hidden />
        Generate package
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Generate router provisioning package</DialogTitle>
            <DialogDescription>
              Download a RouterOS package for <span className="font-medium text-foreground">{routerName}</span> with
              an `.rsc` script, captive portal pages, and a short import guide.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="prov-portal-base">Portal base URL</Label>
              <Input
                id="prov-portal-base"
                value={portalBaseUrl}
                onChange={(e) => setPortalBaseUrl(e.target.value)}
                placeholder="https://wifi.example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-api-base">API base URL</Label>
              <Input
                id="prov-api-base"
                value={apiBaseUrl}
                onChange={(e) => setApiBaseUrl(e.target.value)}
                placeholder="https://api.example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-hotspot-interface">HotSpot interface</Label>
              <Input
                id="prov-hotspot-interface"
                value={hotspotInterface}
                onChange={(e) => setHotspotInterface(e.target.value)}
                placeholder="bridge-hotspot"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-wan-interface">WAN interface</Label>
              <Input id="prov-wan-interface" value={wanInterface} onChange={(e) => setWanInterface(e.target.value)} placeholder="ether1" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-lan-cidr">LAN gateway / CIDR</Label>
              <Input id="prov-lan-cidr" value={lanCidr} onChange={(e) => setLanCidr(e.target.value)} placeholder="10.10.10.1/24" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-dns-name">HotSpot DNS name</Label>
              <Input
                id="prov-dns-name"
                value={dnsName}
                onChange={(e) => setDnsName(e.target.value)}
                placeholder="login.example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-pool-start">DHCP pool start</Label>
              <Input
                id="prov-pool-start"
                value={dhcpPoolStart}
                onChange={(e) => setDhcpPoolStart(e.target.value)}
                placeholder="10.10.10.10"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-pool-end">DHCP pool end</Label>
              <Input
                id="prov-pool-end"
                value={dhcpPoolEnd}
                onChange={(e) => setDhcpPoolEnd(e.target.value)}
                placeholder="10.10.10.250"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-html-dir">HotSpot files directory</Label>
              <Input
                id="prov-html-dir"
                value={hotspotHtmlDirectory}
                onChange={(e) => setHotspotHtmlDirectory(e.target.value)}
                placeholder="esn-hotspot-hq or flash/esn-hotspot-hq"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-cert">SSL certificate name</Label>
              <Input
                id="prov-cert"
                value={sslCertificateName}
                onChange={(e) => setSslCertificateName(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="prov-extra-hosts">Extra walled-garden hosts</Label>
              <Input
                id="prov-extra-hosts"
                value={extraHosts}
                onChange={(e) => setExtraHosts(e.target.value)}
                placeholder="checkout.example.com, cdn.example.com"
              />
              <p className="text-xs text-muted-foreground">
                Add payment gateway or CDN hosts here when guests must reach them before authentication.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-provider-templates">Provider templates</Label>
              <Input
                id="prov-provider-templates"
                value={providerTemplates}
                onChange={(e) => setProviderTemplates(e.target.value)}
                placeholder="clickpesa"
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated templates that add known provider hosts to the walled garden.
              </p>
            </div>
          </div>

          <div className="grid gap-3 rounded-xl border border-border/60 bg-muted/20 p-4 text-sm sm:grid-cols-2">
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                className="mt-1"
                checked={autoDnsStatic}
                onChange={(e) => setAutoDnsStatic(e.target.checked)}
              />
              <span>
                <span className="block font-medium text-foreground">Create DNS static record</span>
                <span className="text-muted-foreground">Maps the HotSpot DNS name to the router gateway automatically.</span>
              </span>
            </label>
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                className="mt-1"
                checked={autoIssueLetsEncrypt}
                onChange={(e) => setAutoIssueLetsEncrypt(e.target.checked)}
              />
              <span>
                <span className="block font-medium text-foreground">Attempt Let&apos;s Encrypt</span>
                <span className="text-muted-foreground">Requires public DNS and WAN reachability on port 80.</span>
              </span>
            </label>
          </div>

          <p className="text-xs text-muted-foreground">
            Use <strong>Push to router</strong> when this router already allows FTP with the same admin credentials.
          </p>

          <div className="rounded-xl border border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground">
            The package keeps your current portal flow intact. It prepares branded hotspot pages, DNS, and RouterOS
            bootstrap config. ESN can now authorize paid devices on RouterOS directly after payment or voucher success.
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={downloadM.isPending || pushM.isPending}>
              Close
            </Button>
            <Button type="button" variant="outline" onClick={() => pushM.mutate()} disabled={downloadM.isPending || pushM.isPending}>
              {pushM.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <WandSparkles className="h-4 w-4" aria-hidden />}
              Push to router
            </Button>
            <Button type="button" onClick={() => downloadM.mutate()} disabled={downloadM.isPending || pushM.isPending}>
              {downloadM.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Download className="h-4 w-4" aria-hidden />}
              Download zip
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
