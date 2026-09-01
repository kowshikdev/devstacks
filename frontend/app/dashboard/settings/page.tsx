"use client";

import { useState } from "react";

import AppShell from "../../../components/AppShell";
import { toHeaderUser, useProfile } from "../../../lib/hooks/useProfile";
import { clearConnection } from "../../../lib/connections";
import { signOut } from "../../../lib/supabase/client";
import { useTheme, type ThemePreference } from "../../../components/ThemeProvider";
import { Avatar } from "../../../components/ui/Avatar";
import { Button, ButtonLink } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { CopyButton } from "../../../components/ui/CopyButton";
import { Dialog } from "../../../components/ui/Dialog";
import { Flash, Skeleton } from "../../../components/ui/Feedback";
import { Label } from "../../../components/ui/Label";
import { ButtonTabs } from "../../../components/ui/Tabs";
import { useToast } from "../../../components/ui/Toast";
import {
  GlobeIcon,
  LockIcon,
  MonitorIcon,
  MoonIcon,
  SignOutIcon,
  SunIcon,
} from "../../../components/ui/Icon";

const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export default function SettingsPage() {
  const { profile, loading } = useProfile();
  const { preference, setPreference } = useTheme();
  const { toast } = useToast();
  const [signOutOpen, setSignOutOpen] = useState(false);

  const profileUrl =
    typeof window !== "undefined" && profile ? `${window.location.origin}/${profile.handle}` : "";

  return (
    <AppShell user={toHeaderUser(profile)}>
      <div className="page-header">
        <div>
          <span className="eyebrow">Settings</span>
          <h1 className="page-header__title mt-1">Profile and account</h1>
          <p className="page-header__description">
            Identity, visibility, and appearance. Anything that changes what the public sees is a
            deliberate action, never a side effect.
          </p>
        </div>
      </div>

      <div className="stack gap-5" style={{ maxWidth: 760 }}>
        <Card>
          <CardHeader title="Identity" />
          <CardBody>
            {loading ? (
              <div className="row gap-4">
                <Skeleton width={56} height={56} radius={999} />
                <div className="flex-1 stack gap-2">
                  <Skeleton width="45%" height={16} />
                  <Skeleton width="30%" height={12} />
                </div>
              </div>
            ) : profile ? (
              <>
                <div className="row gap-4">
                  <Avatar name={profile.display_name ?? profile.handle} size={56} />
                  <div className="flex-1">
                    <p className="font-semibold">{profile.display_name ?? profile.handle}</p>
                    <p className="text-sm text-muted font-mono">@{profile.handle}</p>
                  </div>
                </div>

                <div className="mt-5 stack gap-2">
                  <p className="text-sm font-semibold">Public profile URL</p>
                  <div className="embed-box">
                    <code className="embed-box__code">{profileUrl}</code>
                    <CopyButton value={profileUrl} label="Copy" variant="invisible" />
                  </div>
                  <p className="text-xs text-subtle">
                    A handle is permanent once claimed — it is the stable identifier other systems
                    cite when they reference your evidence.
                  </p>
                </div>
              </>
            ) : null}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Visibility" />
          <CardBody>
            <div className="row row--between row--wrap gap-4">
              <div className="flex-1">
                <p className="text-sm font-semibold">Public profile</p>
                <p className="text-xs text-muted mt-1" style={{ maxWidth: "60ch" }}>
                  Your profile becomes public the moment a claim revision is published. Visibility is
                  a consequence of publishing decisions rather than a switch, so nothing can go
                  public without a claim behind it.
                </p>
              </div>
              {profile?.is_public ? (
                <Label tone="success" size="lg">
                  <GlobeIcon size={13} />
                  Public
                </Label>
              ) : (
                <Label tone="attention" size="lg">
                  <LockIcon size={13} />
                  Not published
                </Label>
              )}
            </div>

            {!profile?.is_public ? (
              <div className="mt-4">
                <Flash tone="info">
                  Publish an approved claim revision from the review inbox to make your profile
                  reachable.
                </Flash>
              </div>
            ) : null}

            <div className="row row--wrap gap-2 mt-4">
              <ButtonLink href="/dashboard/review">Open review inbox</ButtonLink>
              {profile ? (
                <ButtonLink
                  href={`/${profile.handle}`}
                  variant="invisible"
                  leadingIcon={<GlobeIcon size={15} />}
                >
                  View public profile
                </ButtonLink>
              ) : null}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Appearance" />
          <CardBody>
            <div className="row row--between row--wrap gap-4">
              <div className="flex-1">
                <p className="text-sm font-semibold">Theme</p>
                <p className="text-xs text-muted mt-1">
                  Applied before first paint, so switching never flashes.
                </p>
              </div>
              <ButtonTabs
                value={preference}
                onChange={setPreference}
                options={THEME_OPTIONS}
                label="Theme preference"
              />
            </div>
            <div className="row gap-4 mt-4 text-xs text-subtle">
              <span className="row gap-1">
                <SunIcon size={13} /> Light
              </span>
              <span className="row gap-1">
                <MoonIcon size={13} /> Dark
              </span>
              <span className="row gap-1">
                <MonitorIcon size={13} /> Follows your device
              </span>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Session" />
          <CardBody>
            <div className="row row--between row--wrap gap-4">
              <div className="flex-1">
                <p className="text-sm font-semibold">Sign out</p>
                <p className="text-xs text-muted mt-1">
                  Ends this browser session. Connector authorizations stay intact and are revoked
                  from the connections page.
                </p>
              </div>
              <Button
                variant="danger"
                onClick={() => setSignOutOpen(true)}
                leadingIcon={<SignOutIcon size={15} />}
              >
                Sign out
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>

      <Dialog
        open={signOutOpen}
        onClose={() => setSignOutOpen(false)}
        title="Sign out of DevStacks?"
        description="Your published profile stays exactly as it is."
        footer={
          <>
            <Button onClick={() => setSignOutOpen(false)}>Cancel</Button>
            <Button
              variant="danger"
              onClick={() => {
                clearConnection();
                void signOut()
                  .then(() => {
                    window.location.href = "/login";
                  })
                  .catch(() => {
                    toast({ title: "Sign out failed", tone: "danger" });
                    setSignOutOpen(false);
                  });
              }}
            >
              Sign out
            </Button>
          </>
        }
      />
    </AppShell>
  );
}
