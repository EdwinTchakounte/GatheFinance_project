"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";


export default function EpargneClassiqueRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/epargne/depot?context=epargne-classique");
  }, [router]);
  return (
    <main className="min-h-svh bg-cream py-16">
      <Container className="max-w-md">
        <p className="text-center text-ink-600">
          Redirection vers le dépôt épargne classique…
        </p>
      </Container>
    </main>
  );
}
