import { redirect } from "next/navigation";

export default function JobsPage() {
  redirect("/saved?view=pipeline");
}
