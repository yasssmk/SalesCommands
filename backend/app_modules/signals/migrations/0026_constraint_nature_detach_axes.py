# Constraint: add `nature` classification axis and detach from what × dimension.
#
# - Adds ConstraintSignal.nature (required). Existing rows are backfilled with
#   'FUNCTIONAL' as a one-off migration default; the field itself carries NO
#   model default (preserve_default=False) — a nature must be supplied on create.
# - Makes legacy what / dimension nullable (non-destructive: columns kept for
#   historical rows, no longer authored).
# - Drops the now-dead what / dimension / canonical_key indexes and adds the
#   nature index.
#
# Reversible: reverting drops `nature`, restores what/dimension to NOT NULL and
# the previous index set. (Rows created after this migration with NULL
# what/dimension would block the reverse NOT NULL restore — expected for a
# forward-only data shape; the reverse is provided for schema symmetry on a
# freshly-migrated/empty table.)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0025_signals_is_domain_valid"),
    ]

    operations = [
        # --- nature: new required classification axis (backfill existing rows) ---
        migrations.AddField(
            model_name="constraintsignal",
            name="nature",
            field=models.CharField(
                choices=[
                    ("FUNCTIONAL", "Functional"),
                    ("TECHNICAL", "Technical"),
                    ("FINANCIAL", "Financial"),
                    ("CONTRACTUAL", "Contractual & Legal"),
                    ("OPERATIONAL", "Operational"),
                    ("SECURITY", "Security"),
                ],
                default="FUNCTIONAL",
                help_text=(
                    "Kind of decision criterion (FUNCTIONAL / TECHNICAL / "
                    "FINANCIAL / CONTRACTUAL / OPERATIONAL / SECURITY). The "
                    "classification axis for constraints — replaces the "
                    "business what × dimension axes."
                ),
                max_length=20,
                verbose_name="Nature",
            ),
            preserve_default=False,
        ),
        # --- what / dimension: legacy, now nullable ---
        migrations.AlterField(
            model_name="constraintsignal",
            name="what",
            field=models.CharField(
                blank=True,
                choices=[
                    ("OPS", "Operations / Process"),
                    ("TECH", "Technology / System"),
                    ("DATA", "Data / Visibility"),
                    ("PEOPLE", "People / Org"),
                    ("GROWTH", "Growth / Revenue"),
                ],
                help_text=(
                    "LEGACY domain axis — deprecated for constraints, kept "
                    "nullable for historical rows"
                ),
                max_length=20,
                null=True,
                verbose_name="What",
            ),
        ),
        migrations.AlterField(
            model_name="constraintsignal",
            name="dimension",
            field=models.CharField(
                blank=True,
                choices=[
                    ("TIME", "Time / Speed"),
                    ("COST", "Cost / Budget"),
                    ("QUALITY", "Quality / Accuracy"),
                    ("SCALE", "Scale / Capacity"),
                    ("RISK", "Risk / Compliance"),
                ],
                help_text=(
                    "LEGACY friction axis — deprecated for constraints, kept "
                    "nullable for historical rows"
                ),
                max_length=20,
                null=True,
                verbose_name="Dimension",
            ),
        ),
        # --- indexes: drop dead axes, add nature ---
        migrations.RemoveIndex(
            model_name="constraintsignal",
            name="constsig_what_idx",
        ),
        migrations.RemoveIndex(
            model_name="constraintsignal",
            name="constsig_dimension_idx",
        ),
        migrations.RemoveIndex(
            model_name="constraintsignal",
            name="constsig_account_canon_idx",
        ),
        migrations.AddIndex(
            model_name="constraintsignal",
            index=models.Index(fields=["nature"], name="constsig_nature_idx"),
        ),
    ]
