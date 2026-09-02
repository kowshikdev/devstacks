import { PublicShell } from "../../components/AppShell";
import { ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/Feedback";
import { SearchIcon } from "../../components/ui/Icon";

export default function ProfileNotFound() {
  return (
    <PublicShell>
      <div className="container container--md">
        <Card>
          <EmptyState
            icon={<SearchIcon size={20} />}
            title="Nothing published here"
            description="This profile or claim does not exist, or nothing has been published under it yet. A DevStacks profile becomes reachable only once its owner publishes a claim."
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
