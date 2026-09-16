"""Commented schema shared by all item-description DB files and regeneration."""

def database_header(role):
    purpose={
        'index':'Entry point. Loads generated descriptors, then local overrides.',
        'generated':'GENERATED DATA. Do not hand-edit Body; regeneration replaces it.',
        'import':'Local overrides. Edit this file for manually authored descriptions.',
        'template':'Template for db/import/item_description_db.yml; not loaded directly.',
    }[role]
    text=f'''###########################################################################
# Banquet of Heroes - Item Description Database
# Schema: ITEM_DESCRIPTION_DB, Version: 1
###########################################################################
# {purpose}
#
# PURPOSE AND OWNERSHIP
# Describes item/option effects for the structured Item Description UI.
# These records are display metadata, not executable item scripts. Gameplay
# stays in item_db, item_randomopt_db, refine/grade DBs and the map server.
# Item names/art still resolve through the client's catalog by numeric ItemId.
# Do not use this DB to change item stats or to invent evaluated script totals.
#
# LOAD ORDER AND OVERRIDES
#   db/item_description_db.yml
#     -> db/item_description_generated.yml
#     -> db/import/item_description_db.yml
# Later explicitly supplied fields replace earlier values for the same Kind/Id.
# Omitted fields retain earlier values. Effects REPLACES the entire effect list;
# it does not append. Include the item's grade effects when replacing that list.
# Effects: [] intentionally clears all inherited effects for that record.
# The import-tmpl copy is documentation/setup material, not an active import.
#
# GENERATION AND RELOAD
# Generator: WARP20250716-main/tools/generate_item_description_data.py
# Run from the WARP checkout (default server is the sibling BanquetOfHeroes):
#   .\\.venv-target-hud\\Scripts\\python.exe tools/generate_item_description_data.py
#   .\\.venv-target-hud\\Scripts\\python.exe tools/generate_item_description_data.py --check
# The generator follows effective pre-renewal item/option/skill YAML imports.
# It translates supported static statements and verified grade predicates;
# it never executes scripts or parses itemInfo Lua at render time.
# Unsupported/conditional parts retain Legacy/Unknown notices and are audited
# in WARP Outputs/ItemDescription/generated-data-report.json.
# After changing these files: @reloaditemdb, then reopen the item description.
# Invalid imports are rejected transactionally; the last valid descriptors stay.
# A descriptor-only edit does not require a client or map-server rebuild.
#
# RECORD FIELDS
# - Id:             Required positive numeric ID from the effective gameplay DB.
#                   Item and RandomOption IDs use separate namespaces.
#   Kind:           Item (default) or RandomOption. Case-sensitive.
#   Label:          Optional UTF-8 label, max 47 bytes. Used for an option's raw
#                   value row when Effects is empty; does not rename an item.
#   Rarity:         Optional display-only rarity, max 31 UTF-8 bytes. Separate
#                   from numeric enchant grade and the title-color database.
#   Enchantment:    false (default). true classifies a card-backed item ID as
#                   an enchantment component; does not create gameplay slots.
#   Legacy:         false (default). true retains an Original notice for script
#                   effects that this descriptor does not fully describe.
#   Effects:        Sequence of at most 64 effect definitions; [] is valid.
#
# EFFECT FIELDS
# - Text:           Required plain UTF-8 text, max 2048 bytes. No embedded NUL.
#                   Not a Script block, Lua function, HTML, or color-code list.
#   Section:        NativeEffects (default), BaseAttributes, Refine, Grade,
#                   or CardSet. Card/option consumers select their own section.
#   Label:          Optional row label, max 47 UTF-8 bytes (not an item title).
#   MinRefine:      Inclusive minimum refine, 0..255; default 0.
#   MinGrade:       Inclusive minimum grade, 0..255; default 0.
#   MaxGrade:       Inclusive maximum grade, 0..255; default 255.
#                   Must be >= MinGrade. Equal bounds select one exact tier.
#                   Banquet: None=0, Rare=1, Epic=2, Mythic=3, Legendary=4, S=5.
#                   MinGrade: 4 / MaxGrade: 255 also includes S.
#   RequiredCards:  Up to four real component IDs required on THIS item instance.
#                   Duplicate IDs require duplicate slots. This is not a check
#                   of the character's complete equipped set or another item.
#   Unknown:        false (default). true displays an informational effect;
#                   it must not imply a condition was evaluated as active.
#
# CONDITIONS AND LIMITS
# Refine/grade/card predicates are combined with AND. Actual owned-item values
# select Active/Inactive; catalog-only descriptions cannot evaluate an instance.
# Arbitrary BaseLevel/job/map/skill conditions are not evaluated by this schema.
# Keep those explicit in prose/Unknown records and retain Legacy where needed.
# Snapshots have a 64-row budget, including mandatory stats/components/rules.
# Long Text can span several rows; overflow is marked in the UI. Be concise.
#
# RANDOM-OPTION TEXT PLACEHOLDERS (substituted from the actual rolled value)
#   {{value}}             Raw integer, without an added plus sign.
#   {{signed_value}}      Signed integer, e.g. +4 or -4.
#   {{neg_value}}         Negated signed value, e.g. 4 becomes -4.
#   {{value_div10}}       Integer /10, truncated toward zero, with a sign.
#   {{value_tenths}}      Signed decimal /10 (weight units), e.g. +0.4.
#   {{value_hundredths}}  Signed decimal /100, e.g. +0.04.
# Use a unit/sign matching the actual option script; do not guess percentages.
#
# COMMENTED EXAMPLES (not active records; replace Body: [] before using)
# Body:
#   - Id: 4001                  # Poring Card: complete static effects
#     Kind: Item
#     Legacy: false
#     Effects:
#       - Section: NativeEffects
#         Text: "LUK +2"
#       - Section: NativeEffects
#         Text: "Perfect Dodge +1"
#   - Id: 1201                  # Knife: replace the complete grade effect list
#     Legacy: false
#     Effects:
#       - Section: Grade
#         Label: Rare
#         MinGrade: 1
#         MaxGrade: 1
#         Text: "ATK +1%"
#       - Section: Grade
#         Label: Epic
#         MinGrade: 2
#         MaxGrade: 2
#         Text: "ATK +2%"
#       - Section: Grade
#         Label: Mythic
#         MinGrade: 3
#         MaxGrade: 3
#         Text: "ATK +3%"
#       - Section: Grade
#         Label: Legendary / S
#         MinGrade: 4
#         Text: "ATK +5%"
#   - Id: 4                     # Actual random-option ID, not an ItemId
#     Kind: RandomOption
#     Label: AGI
#     Effects:
#       - Text: "AGI {{signed_value}}"
###########################################################################

'''
    return text
