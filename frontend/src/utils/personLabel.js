// frontend/src/utils/personLabel.js
//
// Sprint Next steps 5.9b — the ONE person label of the Activity surfaces (the
// creation / edit drawer, the Context section): users (owner, invited) and
// contacts. Reads first_name / last_name (or full_name) — the auth user
// (useAuth, core.auth_service.auth_user_payload) and the serializers
// (ActivityUserSerializer, contacts) both carry them.

// The person's full name: full_name, else first + last ("" without any).
export function personFullName(person) {
  return (
    person?.full_name ||
    `${person?.first_name ?? ""} ${person?.last_name ?? ""}`.trim()
  );
}

// A person row's name: the full name, else the email (null without any).
export function personName(person) {
  if (!person) return null;
  return personFullName(person) || person.email || null;
}

// « First Last · email » as { name, email }: the email ONCE — as the name —
// when the name is truly missing (email null then).
export function personNameAndEmail(person) {
  const fullName = personFullName(person);
  return {
    name: fullName || person?.email || null,
    email: fullName ? person?.email || null : null,
  };
}
