"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError, type Identity } from "@/lib/api";


export default function ProfilPage() {
  const router = useRouter();
  const [me, setMe] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form infos
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [savingInfo, setSavingInfo] = useState(false);
  const [infoFlash, setInfoFlash] = useState<{ ok: boolean; msg: string } | null>(null);

  // Form password
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [savingPwd, setSavingPwd] = useState(false);
  const [pwdFlash, setPwdFlash] = useState<{ ok: boolean; msg: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    portalApi.me()
      .then((data) => {
        if (cancelled) return;
        setMe(data);
        setFirstName(data.first_name ?? "");
        setLastName(data.last_name ?? "");
        const m = (data.member as { phone?: string } | null) ?? null;
        setPhone(m?.phone ?? "");
      })
      .catch((err: ApiError) => {
        if (err.status === 401 || err.status === 403) router.replace("/connexion");
        else setError(err.detail ?? "Impossible de charger le profil.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [router]);

  async function onSaveInfo(e: React.FormEvent) {
    e.preventDefault();
    setSavingInfo(true);
    setInfoFlash(null);
    try {
      const updated = await portalApi.profile.update({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
      });
      setMe(updated);
      setInfoFlash({ ok: true, msg: "Informations mises à jour." });
    } catch (err) {
      const apiErr = err as ApiError;
      setInfoFlash({ ok: false, msg: apiErr.detail ?? "Échec de la mise à jour." });
    } finally {
      setSavingInfo(false);
    }
  }

  async function onSavePwd(e: React.FormEvent) {
    e.preventDefault();
    if (newPwd !== confirmPwd) {
      setPwdFlash({ ok: false, msg: "Les deux nouveaux mots de passe ne correspondent pas." });
      return;
    }
    if (newPwd.length < 8) {
      setPwdFlash({ ok: false, msg: "8 caractères minimum pour le nouveau mot de passe." });
      return;
    }
    setSavingPwd(true);
    setPwdFlash(null);
    try {
      await portalApi.profile.changePassword(currentPwd, newPwd);
      setPwdFlash({ ok: true, msg: "Mot de passe mis à jour." });
      setCurrentPwd(""); setNewPwd(""); setConfirmPwd("");
    } catch (err) {
      const apiErr = err as ApiError;
      setPwdFlash({ ok: false, msg: apiErr.detail ?? "Échec du changement de mot de passe." });
    } finally {
      setSavingPwd(false);
    }
  }

  if (loading) return <Loader />;
  if (error) return <ErrState msg={error} />;

  return (
    <main className="min-h-svh bg-cream py-10">
      <Container className="max-w-3xl">
        <header className="mb-8">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
            Profil
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900 sm:text-4xl">
            Mes informations.
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            Édite tes coordonnées et ton mot de passe. Les modifications sont
            tracées dans l'audit.
          </p>
          <div className="mt-4">
            <a
              href="/profil/preferences-notifications"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:underline"
            >
              Préférences de notifications →
            </a>
          </div>
        </header>

        {/* ───── Frais d'adhésion (accès PERMANENT — parité mobile) ─────
            Auparavant le paiement des 3 frais (13 000 XAF) n'était atteignable
            que via le CTA « suspendu » de l'accueil. Cette carte l'expose en
            permanence : règlement si le compte n'est pas activé, sinon accès à
            l'historique (reçus). */}
        {me?.member ? (
          me.member.statut === "suspendu" ? (
            <section className="mb-8 rounded-xl border border-amber-300/60 bg-amber-50/60 p-6 shadow-sm">
              <h2 className="font-editorial text-xl text-ink-900">
                Frais d'adhésion
              </h2>
              <p className="mt-1 text-sm text-ink-700">
                Ton compte n'est pas encore activé. Règle tes 3 frais d'adhésion
                (adhésion 10 000 · inscription 2 000 · carnet 1 000 ={" "}
                <strong>13 000 XAF</strong>) pour l'activer.
              </p>
              <a
                href="/activation"
                className={buttonClasses({ variant: "success", size: "md" }) + " mt-4 inline-flex"}
              >
                Régler mes frais →
              </a>
            </section>
          ) : (
            <section className="mb-8 rounded-xl border border-line-200 bg-paper p-6 shadow-sm">
              <h2 className="font-editorial text-xl text-ink-900">
                Frais d'adhésion
              </h2>
              <p className="mt-1 text-sm text-ink-700">
                Tes frais d'adhésion sont réglés — ton compte est actif. ✓
              </p>
              <a
                href="/paiements"
                className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:underline"
              >
                Voir mes reçus de versement →
              </a>
            </section>
          )
        ) : null}

        {/* ───── Mes infos ───── */}
        <form onSubmit={onSaveInfo} className="mb-8 rounded-xl border border-line-200 bg-paper p-6 shadow-sm">
          <h2 className="font-editorial text-xl text-ink-900">Coordonnées</h2>
          <p className="mt-1 text-sm text-ink-600">
            Email : <span className="font-mono text-ink-900">{me?.email}</span>
            {" "}<span className="text-xs text-ink-500">(non modifiable)</span>
          </p>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Field label="Prénom" id="fn" value={firstName} onChange={setFirstName} />
            <Field label="Nom" id="ln" value={lastName} onChange={setLastName} />
            <Field label="Téléphone" id="ph" value={phone} onChange={setPhone} placeholder="+237 6XX XX XX XX" full />
          </div>

          {infoFlash ? (
            <p className={`mt-4 rounded-lg px-3 py-2.5 text-sm ${
              infoFlash.ok ? "border border-emerald-200 bg-emerald-50/60 text-emerald-700" : "border border-terra-400/40 bg-terra-50/60 text-terra-700"
            }`}>{infoFlash.msg}</p>
          ) : null}

          <div className="mt-5 flex justify-end">
            <button
              type="submit"
              disabled={savingInfo}
              className="inline-flex items-center justify-center rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-800 disabled:opacity-60"
            >
              {savingInfo ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>

        {/* ───── Mot de passe ───── */}
        <form onSubmit={onSavePwd} className="rounded-xl border border-line-200 bg-paper p-6 shadow-sm">
          <h2 className="font-editorial text-xl text-ink-900">Mot de passe</h2>
          <p className="mt-1 text-sm text-ink-600">
            8 caractères minimum. Le changement déconnecte les autres sessions actives.
          </p>

          <div className="mt-5 space-y-4">
            <Field type="password" label="Mot de passe actuel" id="cur" value={currentPwd} onChange={setCurrentPwd} full />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field type="password" label="Nouveau mot de passe" id="new" value={newPwd} onChange={setNewPwd} />
              <Field type="password" label="Confirmer" id="cnf" value={confirmPwd} onChange={setConfirmPwd} />
            </div>
          </div>

          {pwdFlash ? (
            <p className={`mt-4 rounded-lg px-3 py-2.5 text-sm ${
              pwdFlash.ok ? "border border-emerald-200 bg-emerald-50/60 text-emerald-700" : "border border-terra-400/40 bg-terra-50/60 text-terra-700"
            }`}>{pwdFlash.msg}</p>
          ) : null}

          <div className="mt-5 flex justify-end">
            <button
              type="submit"
              disabled={savingPwd}
              className="inline-flex items-center justify-center rounded-lg bg-ink-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-ink-800 disabled:opacity-60"
            >
              {savingPwd ? "Mise à jour…" : "Changer le mot de passe"}
            </button>
          </div>
        </form>
      </Container>
    </main>
  );
}


function Field({ id, label, value, onChange, type = "text", placeholder, full }: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; full?: boolean;
}) {
  return (
    <div className={full ? "sm:col-span-2" : undefined}>
      <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-700" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="block w-full rounded-lg border border-line-200 bg-paper px-3.5 py-2.5 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
      />
    </div>
  );
}

function Loader() {
  return (
    <main className="min-h-svh bg-cream py-16">
      <Container><p className="text-center text-ink-600">Chargement…</p></Container>
    </main>
  );
}

function ErrState({ msg }: { msg: string }) {
  return (
    <main className="min-h-svh bg-cream py-16">
      <Container className="max-w-md">
        <p className="rounded-lg border border-terra-400/40 bg-terra-50/60 p-4 text-sm text-terra-700">{msg}</p>
      </Container>
    </main>
  );
}
