import { PublicShell } from "../components/AppShell";
import { ButtonLink } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/Feedback";
import { SearchIcon } from "../components/ui/Icon";

export default function NotFound() {
  return (
    <PublicShell>
      <div className="container container--md">
        <Card>
          <EmptyState
            icon={<SearchIcon size={20} />}
            title="404 — nothing published here"
            description="This page does not exist, or the profile you asked for has not published a claim yet. A DevStacks profile becomes reachable only once its owner publishes something."
            action={
              <>
                <ButtonLink href="/" variant="primary">
                  Back to home
                </ButtonLink>
                <ButtonLink href="/try">Preview a GitHub username</ButtonLink>
              </>
            }
          />
        </Card>
      </div>
    </PublicShell>
  );
}
