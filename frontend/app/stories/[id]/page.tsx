import { StoryDetailPage } from "@/components/stories/StoryDetailPage";

export default async function StoryRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const storyId = Number(id);
  return <StoryDetailPage storyId={storyId} />;
}
