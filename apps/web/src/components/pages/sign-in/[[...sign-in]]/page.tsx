"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="p-6 w-full max-w-sm space-y-4">
        <h1 className="text-lg font-semibold text-foreground">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          Auth is not configured yet. Plug in your provider (Clerk, Auth.js, Supabase) to enable sign-in.
        </p>
        <Button variant="outline" onClick={() => window.history.back()}>Go back</Button>
      </Card>
    </div>
  );
}
