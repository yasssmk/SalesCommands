# Inventaire People ↔ Contact

> **Origine** : audit read-only du sprint Next steps (surface Activity), sous-étape **5.8g**, validé par le PO
> (« très bon, gardé pour le chantier DC ») et versionné à la clôture du sprint (décision 5.8h).
> **Dette associée** : **TD-307** « Modèle Personnes (People / Contact / rôle) » (TECH_DEBT.md).
> **Nature** : photographie à la date de l'audit (branche `feat/ux-activity-next-steps`, avant la 5.8h) — les
> références `fichier:ligne` peuvent avoir bougé depuis. Faits seulement : aucune décision de modèle n'est prise ici.

## Ce qui a changé depuis l'audit (clôture du sprint Next steps)

- **Incohérence 22** (« create-with-entities ignore les invités ») : **corrigée** en 5.8h (`53a1d45a`).
- **Incohérence 14** (« un PS REJECTED peut rester cité ») : **corrigée pour cited-contacts et le pré-remplissage** en 5.8h (`a9f44697`).
- **Incohérence 18** (« pré-remplissage asymétrique ») : **corrigée** en 5.8h (`a65006aa`) — les personnes citées ne deviennent des contacts que pour MEETING / CALL / EMAIL, `target_contact` compris.
- **Incohérence 16** (« la conversion d'un next step contredit sa documentation ») : **corrigée** en 5.8h (`3cc4fc43`, migration `module_signals/0048`, `help_text` seul) — le serveur n'ajoute aucun contact, la doc le dit.
- **Incohérence 37** / ligne 60 (« composants morts qui affichent des personnes ») : `ActivityOverviewTab` et `SignalDetailCard` **supprimés** au bloc 6 (`9d9a21fb`, `6b9cd617`) ; `DecisionStepDetail.jsx` existe toujours (TD-180).
- Les autres points sont **inchangés**.

## Inventaire (60 opérations) et incohérences (37)

Préfixes : **B/** = `backend/app_modules/`, **F/** = `frontend/src/`. Objets : PS = PeopleSignal, C = Contact, U = User.

| # | Moment | Objet | Opération | Par qui | Surface | fichier:ligne |
|---|---|---|---|---|---|---|
| 1 | Modèle PeopleSignal | PS → C, département, DC, activité, U | modèle | – | – | B/signals/models/people_signal.py:78-89, 107-121, 127-153, 198-246 ; base_model.py:78, 117, 127, 212, 234, 267 |
| 2 | Extraction People (dernière étape du pipeline) | PS PENDING, `target_contact` | créé + relié | LLM (people_v1, contexte v9) | Activity | B/ai_pipelines/pipelines/transcript_signals.py:220-233 ; prompts/transcript_signals/people_v1.py:30-77 ; services/transcript_signal_extractor.py:1396-1534 |
| 3 | Rapprochement nom → contact (People, Blocker) | C de l'activité | relié | système, `resolve_participant_by_name` (égalité → aucun lien) | post-traitement LLM | B/ai_pipelines/services/participant_refs.py:37-50, 113-172 |
| 4 | Dédoublonnage People pendant l'extraction | PS | dédoublonnage | système | Activity | transcript_signal_extractor.py:622-661 |
| 5 | Vérification de preuve (locuteur, nom dans la citation) | PS | lu ; rôle remis à UNKNOWN si échec | système | Activity | B/ai_pipelines/services/people_evidence.py:50-66 ; participant_refs.py:214-235 |
| 6 | Propagation DC / campagne | PS | DC / campagne recopiés depuis l'activité source | système (SignalManager) | – | B/signals/services/signal_manager.py:143, 253-262 |
| 7 | Contacts retirés du prompt d'extraction (v8) | C | non lu | contexte LLM | extraction | prompts/transcript_signals/context.py:25-34, 95-97 |
| 8 | Auteur d'un Blocker (« raised by ») | C (`BlockerSignal.contact`) | relié | LLM `raised_by_name` → rapprochement | Activity | B/signals/models/blocker_signal.py:142-155 ; extractor :1257-1261 |
| 9 | Objective PERSONAL `target_contact` | C | jamais renseigné par le LLM | LLM objective | – | objective_signal.py:162-170 ; extractor :984-997 |
| 10 | Endpoint People du DC | PS VALIDATED + C | lu (qualifiés / non qualifiés) | PeopleConsolidationService | DC | B/decision_cycles/views/views.py:890-908 ; services/people_consolidation_service.py:37-183 |
| 11 | Onglet People du DC | PS, C | affiché | commercial | DC | F/sections/accounts/dc-workspace/PeopleTab.jsx:97-119, 260-456 |
| 12 | QualifyDialog / « Add Stakeholder » | PS MANUAL, contact choisi, DC, sans activité source | créé + relié | commercial | DC | PeopleTab.jsx:136-244, 460-505 |
| 13 | API create / update People | PS | créé / modifié | commercial (API) | toutes | B/signals/serializers/people_serializer.py:197-358 ; base_serializer.py:373-413 |
| 14 | Drawer d'édition People | PS (`target_contact`, nom, département, rôle) | modifié | commercial | Activity | F/sections/activities/workspace/EditPeopleContent.jsx:130-247 |
| 15 | Détail / ligne People | PS, C | affiché | commercial | Activity, DC | F/components/signals/SignalDetailContent.jsx:1540-1740 ; SignalLine.jsx:289-295 ; signalDisplay.js:134-152 |
| 16 | Clusters People de l'onglet Signals du DC | PS VALIDATED + PENDING | regroupé par personne | SignalClusterService | DC | B/signals/services/signal_cluster_service.py:713-761, 1547-1600, 2370-2460 |
| 17 | Score de readiness (DM / EB / Champion) | PS VALIDATED | lu | système | DC | readiness_score_service.py:43-51, 118-128 |
| 18 | Drawer contact (lecture) | C + rôle PS dans le DC | affiché | commercial | Activity | F/sections/activities/workspace/ContactDrawerContent.jsx:96-149, 239-260 |
| 19 | EditContactContent, identité | C | modifié | commercial | Activity | EditContactContent.jsx:111-149 |
| 20 | EditContactContent, rôle dans la décision | **nouveau PS MANUAL à chaque changement** | lu + créé | commercial (seulement si DC) | Activity → DC | EditContactContent.jsx:94-107, 151-172 |
| 21 | Rôle propre au Contact | `C.influence_level`, `has_buying_authority` | CRUD + affiché | commercial | Account | B/contacts/models.py:17-25, 95-106 ; AccountContactsTab.jsx:303-323 |
| 22 | Personnes d'une activité | C (M2M), U owner, U invités, CampaignContact | modèle | – | – | B/activities/models.py:167-193, 243-251 |
| 23 | Création d'activité (POST) | C (≥ 1, du compte), U invités, owner = créateur | créé | commercial | Activity / DC | B/activities/serializers.py:1025-1066, 1154-1186 |
| 24 | create-with-entities (contact à la volée) | C créé (département General Management), **invités ignorés** | créé + relié | commercial | Activity | B/activities/services/activity_creation_service.py:286-326, 449-531 |
| 25 | Mise à jour d'activité | C, owner, invités (+ notification) | modifié | commercial | Activity | serializers.py:1321-1386, 1467-1475 |
| 26 | Section People d'EditActivityContent | U owner / invités, C, contact à la volée, « Mentioned » | création / édition | commercial | Activity | EditActivityContent.jsx:363-556, 585-698 |
| 27 | ActivityModal (création, ancien chemin) | C, contact à la volée, pas d'owner / invités | créé | commercial | Account | ActivityModal.jsx:154-246, 661-778 |
| 28 | Carte Context de l'activité | U owner / invités, C | affiché | commercial | Activity | ActivityContextSection.jsx:86-89, 226-325 |
| 29 | Données personnes du serializer d'activité | C, U | lu | système | Activity | serializers.py:55-95, 426-428 |
| 30 | Champs personnes du NextStep | PS M2M, noms, noms internes, C M2M (dormant) | modèle | – | – | B/signals/models/next_step_signal.py:223-242, 326-359 |
| 31 | Rattachement des personnes à l'extraction des next steps | PS non REJECTED (DC + activité) par nom ; noms non reliés gardés ; `suggested_contacts` jamais renseigné | créé + relié | LLM next_steps + `resolve_people_signal_by_name` | Activity | next_step_extractor.py:67-71, 268-289, 358-371, 463-477 ; participant_refs.py:175-211 |
| 32 | Serializer NextStep | PS, C | lu | système | Activity, DC | next_step_serializer.py:64-92, 122-144 |
| 33 | Endpoint cited-contacts | `PS.target_contact`, sinon C du compte par nom | lu / résolu | système | Activity (pré-remplissage) | B/signals/services/next_step_cited_names.py:24-48 ; views/next_step_signal_views.py:98-124 |
| 34 | Pré-remplissage de l'activité depuis un next step | C, « Mentioned », noms internes → description | pré-remplissage | commercial | Activity | F/utils/activityTypes.js:93, 115-155 |
| 35 | Matérialisation du next step | – | le serveur n'ajoute aucun contact | système | Activity | B/activities/services/next_step_materialization.py:25 |
| 36 | Lier un next step à une activité existante | C (`target_contact` + `suggested_contacts`), classement + contacts à ajouter | lu + relié | commercial | DC / Activity | B/signals/services/next_step_link_service.py:68-89, 159-168, 227-283 |
| 37 | EditNextStepContent | noms cités | non affichés, non envoyés (5.8g) | commercial | Activity | EditNextStepContent.jsx:14-19 |
| 38 | Pack prep call | C cible (optionnel) + rôle PS ; liste PS du DC ; contact du Blocker | lu → prompt | LLM prep_call | Préparation | prep_call/input_pack_assembler.py:32-145, 311-498 ; prompts/prep_call/context.py:86-160 |
| 39 | Déclenchement du prep call | `contact_id` toujours null | – | commercial | Activity | F/sections/activities/workspace/ActivityPreparationTab.jsx:43-48 |
| 40 | Pack deal health | PS VALIDATED (roster de consolidation + liste PS) ; acteur du Blocker | lu → prompt | LLM deal_health | DC | deal_health_evidence_builder.py:57, 112-120, 187-191, 339-357 ; prompts/deal_health/context.py:77-99 |
| 41 | Contexte next steps | prénoms des contacts des activités ouvertes du DC | lu → prompt | LLM next_steps | Activity | prompts/next_steps/context.py:44-45, 81-83, 127-181 |
| 42 | Formateurs LLM dormants | C | aucun appelant | – | – | base_serializer.py:606-667 ; signal_data_service.py:232-290 |
| 43 | `source_context.contacts` (« qui l'a dit ») | C = tous les contacts de l'activité source | lu / affiché / filtré | système | Activity, DC, Account | base_serializer.py:144-182 ; SignalLine.jsx:217-219 ; SignalDetailContent.jsx:328-340 |
| 44 | Filtres « contact » des signaux | C via contacts de l'activité source | filtre | commercial | Account, DC | B/signals/filters.py:131-146 ; signal_cluster_service.py:1176-1186, 1395-1408 |
| 45 | `distinct_contacts_count` des clusters | C | lu | système | DC / Account | signal_cluster_service.py:2410-2415 |
| 46 | Signaux du compte : People exclus | PS | non affichés | – | Account | AccountSignalsTab.jsx:70-72 ; signal_cluster_service.py:759-761 |
| 47 | Liste des contacts du compte | C | CRUD + affiché | commercial | Account | AccountContactsTab.jsx ; FormContactAdd.jsx ; FormContactEdit.jsx |
| 48 | Owner du compte | U | modèle | – | Account | B/accounts/models.py:144-186 |
| 49 | Stakeholders du DC | C via DecisionStepContact + contacts d'activité ; `DecisionStep.stakeholder` en texte libre | modèle / lu | commercial (ancienne modale) / système | DC | B/decision_cycles/models.py:340, 431-437, 510-516, 685-836 ; completeness_score.py:30, 171 |
| 50 | Contact principal de la timeline du DC | C (premier contact) | affiché | système | DC | decision_cycles/serializers.py:70-86 |
| 51 | Owner du DC, owners des activités | U | modèle / lu | système | DC | decision_cycles/models.py:36-37 |
| 52 | Modèle des personnes de campagne | U owner / exécutant ; C cibles ; `CampaignContact.contact` (NOT NULL) | modèle | – | Campaign | campaigns/models/campaign_contact.py:41-53 ; campaign_account.py:56-70 |
| 53 | Enrôlement de campagne | CampaignContact PENDING | créé | système / commercial | Campaign | campaign_creation_service.py:285-372 |
| 54 | Génération des activités de campagne | `Activity.contacts` + FK `campaign_contact` ; activité de compte avec contact=None | créé + relié | système | Campaign | campaign_execution_service.py:118-268, 520-685 |
| 55 | Affichage des cibles / playlist | contact, `contacts[0]` | affiché | commercial | Campaign | TargetsTab.jsx:99-295 ; PlaylistActivityCard.jsx:140-150 |
| 56 | Verrou d'une activité de campagne | contacts / owner / invités verrouillés | – | – | Activity | EditActivityContent.jsx:621-624 |
| 57 | Reset d'une campagne ciblée | liens C supprimés | supprimé | système | Campaign | backend/end_users/views/user_view.py:1225-1258 |
| 58 | `validated_by` / `requested_by` | U | affiché | système | détail des signaux | base_serializer.py:336-366 |
| 59 | Endpoint des choix (rôles / influences) | PeopleRole / InfluenceLevel | lu | formulaires | toutes | base_views.py:529-563 ; signals/constants.py:165-205 |
| 60 | Composants morts qui affichent des personnes | C / U / PS | non importés | – | – | ActivityOverviewTab.jsx:1782-1786 ; SignalDetailCard.jsx:36, 65 ; DecisionStepDetail.jsx:226, 288 |

### Incohérences constatées (faits seulement)

1. **Trois stockages du rôle / de l'influence d'une même personne**, et deux enums différentes nommées `InfluenceLevel` :
   - côté Contact : `Contact.influence_level` (DECISION_MAKER, CHAMPION…), et `has_buying_authority` ;
   - côté PeopleSignal : `PeopleSignal.role` et `PeopleSignal.influence` (HIGH / MEDIUM / LOW) ;
   - références : B/contacts/models.py:17, B/signals/constants.py:195 ;
   - l'onglet Contacts du compte affiche le champ du Contact sous l'en-tête « Influence ».
2. **Le rôle dans le DC n'est jamais mis à jour** (vérifié) : le drawer contact crée un nouveau PeopleSignal MANUAL à chaque changement. QualifyDialog fait de même, et il n'y a aucun dédoublonnage. Plusieurs PS VALIDATED s'empilent donc pour un même contact dans un même DC (EditContactContent.jsx:151-172 ; PeopleTab.jsx:482-505).
3. **Le « rôle actuel » d'un contact est choisi de trois façons** (vérifié) :
   - le premier par tri `role, -created_at`, donc par ordre alphabétique du rôle et non le plus récent (people_consolidation_service.py:92) ;
   - le plus récent tous DC confondus (prep call, input_pack_assembler.py:128-136) ;
   - par égalité de nom (input_pack_assembler.py:483-489).
4. **Pas d'activité source** sur les PS créés depuis le drawer contact ni depuis QualifyDialog.
5. **Les deux vues People du DC divergent.** L'onglet People ne montre que les VALIDATED, une ligne par signal. Les clusters de l'onglet Signals prennent VALIDATED + PENDING, groupés par personne. Un PS PENDING apparaît donc dans Signals pendant que son contact est « Unqualified » dans People.
6. **Une personne sans contact n'est jamais qualifiée.** Elle peut apparaître deux fois : comme nom, et comme Contact « Unqualified » (people_consolidation_service.py:57-66, 135-183).
7. **Aucun service de réconciliation.** Le modèle l'annonce (people_signal.py:186-191), mais le seul lien automatique se fait à l'extraction. Les clés `contact:<id>` et `name:…|dept:…` coupent une même personne en deux clusters.
8. **Une même règle de nom (TD-279) appliquée à quatre périmètres** :
   - contacts de l'activité ;
   - contacts du compte (cited-contacts) ;
   - People du DC + activité (next steps) ;
   - libellés de locuteur.
   
   S'y ajoutent deux normalisations différentes : accents gardés dans people_signal.py:204-220, retirés dans participant_refs.py:80-84.
9. **Le nom affiché d'une personne suit un ordre de priorité différent selon la surface.** `getPeopleName` donne la priorité au contact, `getCitedPersonName` au full_name ; les clusters, la QualifiedPersonCard, `getPeopleSummary` et les packs deal health / prep call ont chacun leur ordre. Les packs ignorent `full_name`.
10. **Docstring et code se contredisent** : la docstring exige un contact ou un département ; le code accepte un `full_name` seul (people_signal.py:27-73 vs 237-243).
11. **L'extraction contourne `clean()`** et la garde FK du serializer.
12. **Poste en double** : `metadata.job_title`, venu du LLM, et `target_contact.job_title`, lu par l'onglet People.
13. **Département** : le prep call préfère `Contact.department` (texte libre) ; partout ailleurs, c'est `standard_department`.
14. **Un PS REJECTED peut rester cité** (vérifié). L'extraction exclut les REJECTED au moment du rattachement, mais aucun filtre de statut ne s'applique ensuite : cited-contacts, serializer, link service, pré-remplissage.
15. **`suggested_contacts` est dormant, mais encore lu** par le pré-remplissage, le link service, le serializer et `formatSuggestedContacts`.
16. **La conversion d'un next step contredit sa documentation** : l'aide du modèle dit que les contacts deviennent ceux de l'activité ; le service de matérialisation n'en ajoute aucun.
17. **ActivityModal n'appelle pas cited-contacts**, contrairement au drawer de création (ActivityModal.jsx:199).
18. **Pré-remplissage asymétrique** : `target_contact` est ajouté pour tous les types, les contacts résolus par nom seulement pour MEETING / CALL / EMAIL.
19. **« Lier » utilise une troisième règle** : `target_contact` + `suggested_contacts`, sans résolution par nom.
20. **`suggested_internal_names` n'est jamais relié à un User.**
21. **Périmètre des contacts d'activité** : create-with-entities filtre sur le tenant seul ; create et update filtrent sur tenant + compte.
22. **create-with-entities ignore les invités** (vérifié) : voir le défaut signalé en tête.
23. **Contact créé à la volée** : aucune détection de doublon, et département forcé à General Management.
24. **« Qui l'a dit » = tous les contacts inscrits sur l'activité** (vérifié), ce que TD-279 dit ne pas être une preuve de parole (base_serializer.py:144-155 vs prompts/transcript_signals/context.py:25-29).
25. **Les filtres par contact et `distinct_contacts_count`** portent sur les contacts de l'activité, pas sur `target_contact`.
26. **Repli contradictoire** : `getContact()` se rabat sur le premier participant, repli que les détails People et Blocker interdisent.
27. **Blocker non résolu** : son `raised_by_name` est perdu, alors qu'un People garde son `full_name`.
28. **`ObjectiveSignal.target_contact` n'est jamais renseigné** et n'a aucun lien avec les PS.
29. **Contact du prep call inerte** : le front envoie toujours `contact_id = null`, l'API accepte n'importe quel contact du tenant, et les contacts de l'activité ne sont pas dans le pack.
30. **Pack deal health** : les People y figurent deux fois, sous deux formes (roster et liste de PS).
31. **Contexte next steps** : il contient les prénoms des contacts d'autres activités, sans filtre de compte ; ceux de l'activité source sont exclus.
32. **Formateurs LLM morts** (aucun appelant).
33. **Campagne : deux liens activité → contact** (M2M et FK `campaign_contact`).
34. **Activité de compte en campagne : contact absent, partout** (vérifié). `CampaignContact` est créé avec contact=None alors que la colonne est NOT NULL, et l'activité a 0 contact alors que les serializers en exigent au moins 1.
35. **Stakeholders du DC sous trois formes**, sans lien avec les PS. Leur interface n'est importée nulle part.
36. **Contact principal de la timeline** = `.first()` sans tri.
37. **Composants morts qui affichent des personnes** : ActivityOverviewTab, SignalDetailCard.
