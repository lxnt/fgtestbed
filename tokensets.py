__all__ = [ 'MATERIAL_TEMPLATE_TOKENS','MATERIAL_TOKENS','INORGANIC_TOKENS','PLANT_TOKENS','CREATURE_GRAPHICS_TOKENS']

CREATURE_GRAPHICS_TOKENS = set("""
    ADMINISTRATOR ADVISOR ALCHEMIST ANIMAL_CARETAKER ANIMAL_DISSECTOR
    ANIMAL_TRAINER ANIMATED ARCHITECT ARMORER AXEMAN BABY BARON BARON_CONSORT
    BEEKEEPER BLACKSMITH BLOWGUNMAN BONE_CARVER BONE_SETTER BOOKKEEPER
    BOWMAN BOWYER BREWER BROKER BUTCHER CAPTAIN CAPTAIN_OF_THE_GUARD
    CARPENTER CHAMPION CHEESE_MAKER CHIEF_MEDICAL_DWARF CHILD CLERK
    CLOTHIER COOK COUNT COUNT_CONSORT CRAFTSMAN CROSSBOWMAN DEFAULT
    DIAGNOSER DIPLOMAT DOCTOR DRUID DRUNK DUKE DUKE_CONSORT DUNGEON_KEEPER
    DUNGEON_LORD DUNGEONMASTER DUNGEON_MASTER DUNGEON_NASTER DYER
    ENGINEER ENGRAVER EXECUTIONER FARMER FISH_CLEANER FISH_DISSECTOR
    FISHERMAN FISHERY_WORKER FORCED_ADMINISTRATOR FURNACE_OPERATOR
    GEM_CUTTER GEM_SETTER GENERAL GHOST GLASSMAKER GLAZER GRAND_TREASURER
    GUILDREP HAMMERMAN HERBALIST HIGH_PRIEST HOARDMASTER HUNTER JEWELER
    KING KING_CONSORT LASHER LEADER LEATHERWORKER LIEUTENANT LYE_MAKER
    MACEMAN MANAGER MASON MASTER_AXEMAN MASTER_BLOWGUNMAN MASTER_BOWMAN
    MASTER_CROSSBOWMAN MASTER_HAMMERMAN MASTER_LASHER MASTER_MACEMAN
    MASTER_PIKEMAN MASTER_SPEARMAN MASTER_SWORDSMAN MASTER_THIEF
    MASTER_WRESTLER MAYOR MECHANIC MERCHANT MERCHANTBARON MERCHANTPRINCE
    METALCRAFTER METALSMITH MILITIA_CAPTAIN MILITIA_COMMANDER MILKER
    MILLER MINER MONARCH OUTPOSTLIAISON OUTPOST_LIAISON 
    PHILOSOPHER PIKEMAN PLANTER POTASH_MAKER POTTER PRESSER PRIEST PRISONER
    PSYCHIATRIST PUMP_OPERATOR RANGER RECRUIT SHEARER SHERIFF SHOPKEEPER
    SIEGE_ENGINEER SIEGE_OPERATOR SKELETON SLAVE SOAP_MAKER SPEARMAN SPINNER
    STANDARD STONECRAFTER STONEWORKER STRAND_EXTRACTOR SURGEON SUTURER SWORDSMAN
    TANNER TAXCOLLECTOR TAX_COLLECTOR THIEF THRESHER TRADER TRAINED_HUNTER
    TRAINED_WAR TRAPPER TREASURER WAX_WORKER WEAPONSMITH WEAVER WOOD_BURNER
    WOODCRAFTER WOODCUTTER WOODWORKER WRESTLER ZOMBIE
    """.split())
# http://dwarffortresswiki.org/index.php/DF2012:Material_definition_token
MATERIAL_TEMPLATE_TOKENS = set("""
    ABSORPTION
    ALCOHOL
    ALCOHOL_CREATURE
    ALCOHOL_PLANT
    BARREL
    BASIC_COLOR
    BENDING_ELASTICITY
    BENDING_FRACTURE
    BENDING_STRAIN_AT_YIELD
    BENDING_YIELD
    BLOCK_NAME
    BLOOD_MAP_DESCRIPTOR
    BOILING_POINT
    BONE
    BUILD_COLOR
    BUTCHER_SPECIAL
    CHEESE
    CHEESE_CREATURE
    CHEESE_PLANT
    COLDDAM_POINT
    COMPRESSIVE_ELASTICITY
    COMPRESSIVE_FRACTURE
    COMPRESSIVE_STRAIN_AT_YIELD
    COMPRESSIVE_YIELD
    CRYSTAL_GLASSABLE
    DISPLAY_COLOR
    DISPLAY_UNGLAZED
    DO_NOT_CLEAN_GLOB
    EDIBLE_COOKED
    EDIBLE_RAW
    EDIBLE_VERMIN
    ENTERS_BLOOD
    EXTRACT_STORAGE
    FLASK
    GENERATES_MIASMA
    GOO_MAP_DESCRIPTOR
    HARDENS_WITH_WATER
    HEATDAM_POINT
    HORN
    ICHOR_MAP_DESCRIPTOR
    IGNITE_POINT
    IMPACT_FRACTURE
    IMPACT_YIELD
    IMPACT_STRAIN_AT_YIELD
    IMPLIES_ANIMAL_KILL
    IS_GEM
    IS_GLASS
    IS_METAL
    IS_STONE
    ITEMS_AMMO
    ITEMS_ANVIL
    ITEMS_ARMOR
    ITEMS_BARRED
    ITEMS_DELICATE
    ITEMS_DIGGER
    ITEMS_HARD
    ITEMS_LEATHER
    ITEMS_METAL
    ITEMS_QUERN
    ITEMS_SCALED
    ITEMS_SIEGE_ENGINE
    ITEMS_SOFT
    ITEMS_WEAPON
    ITEMS_WEAPON_RANGED
    ITEM_SYMBOL
    LEAF_MAT
    LEATHER
    LIQUID_DENSITY
    LIQUID_MISC
    LIQUID_MISC_CREATURE
    LIQUID_MISC_OTHER
    LIQUID_MISC_PLANT
    MATERIAL_REACTION_PRODUCT
    MATERIAL_VALUE
    MAT_FIXED_TEMP
    MAX_EDGE
    MEAT
    MEAT_NAME
    MELTING_POINT
    MOLAR_MASS
    NO_STONE_STOCKPILE
    PEARL
    POWDER_DYE
    POWDER_MISC
    POWDER_MISC_CREATURE
    POWDER_MISC_PLANT
    PUS_MAP_DESCRIPTOR
    REACTION_CLASS
    ROTS
    SEED_MAT
    SHEAR_ELASTICITY
    SHEAR_FRACTURE
    SHEAR_STRAIN_AT_YIELD
    SHEAR_YIELD
    SHELL
    SILK
    SLIME_MAP_DESCRIPTOR
    SOAP
    SOAP_LEVEL
    SOLID_DENSITY
    SPEC_HEAT
    STATE_ADJ
    STATE_COLOR
    STATE_NAME
    STATE_NAME_ADJ
    STOCKPILE_GLOB
    STOCKPILE_GLOB_PASTE
    STOCKPILE_GLOB_PRESSED
    STOCKPILE_GLOB_SOLID
    STOCKPILE_THREAD_METAL
    STONE_NAME
    STRUCTURAL_PLANT_MAT
    SYN_AFFECTED_CREATURE
    SYN_IMMUNE_CLASS
    SYN_IMMUNE_CREATURE
    TEMP_DIET_INFO
    TENSILE_ELASTICITY
    TENSILE_FRACTURE
    TENSILE_STRAIN_AT_YIELD
    TENSILE_YIELD
    THREAD_PLANT
    TILE
    TILE_COLOR
    TOOTH
    TORSION_ELASTICITY
    TORSION_FRACTURE
    TORSION_STRAIN_AT_YIELD
    TORSION_YIELD
    UNDIGGABLE
    WOOD
    YARN """.split())

# "Not permitted in material template definitions" tokens
# from the above url 
MATERIAL_TOKENS = set("""
    IF_EXISTS_SET_BOILING_POINT
    IF_EXISTS_SET_COLDDAM_POINT
    IF_EXISTS_SET_HEATDAM_POINT
    IF_EXISTS_SET_IGNITE_POINT
    IF_EXISTS_SET_MAT_FIXED_TEMP
    IF_EXISTS_SET_MELTING_POINT
    MULTIPLY_VALUE
    PREFIX """.split())
# not seen in std templates
SYNDROME_TOKENS = set("""
    SYNDROME
    SYN_NAME
    SYN_INJECTED
    SYN_INGESTED
    SYN_CONTACT
    SYN_INHALED
    SYN_AFFECTED_CLASS
    SYN_IMMUNE_CLASS
    SYN_AFFECTED_CREATURE
    SYN_IMMUNE_CREATURE
    CE_PAIN
    CE_SWELLING
    CE_OOZING
    CE_BRUISING
    CE_BLISTERS
    CE_NUMBNESS
    CE_PARALYSIS
    CE_FEVER
    CE_BLEEDING
    CE_COUGH_BLOOD
    CE_VOMIT_BLOOD
    CE_NAUSEA
    CE_UNCONSCIOUSNESS
    CE_NECROSIS
    CE_IMPAIR_FUNCTION
    CE_DROWSINESS
    CE_DIZZINESS
    
    CE_ADD_TAG
    CE_REMOVE_TAG
    CE_DISPLAY_TILE 
    CE_DISPLAY_NAME 
    CE_FLASH_TILE 
    CE_PHYS_ATT_CHANGE 
    CE_MENT_ATT_CHANGE 
    CE_BODY_APPEARANCE_MODIFIER 
    CE_BP_APPEARANCE_MODIFIER 
    CE_MATERIAL_FORCE_MULTIPLIER 
    CE_BODY_MAT_INTERACTION 
    CE_SPEED_CHANGE 
    CE_CAN_DO_INTERACTION 
    CE_BODY_TRANSFORMATION 
    CE_SKILL_ROLL_ADJUST 
    """.split())

# http://dwarffortresswiki.org/index.php/DF2012:Inorganic_material_definition_token
INORGANIC_TOKENS = set("""
    WAFERS
    DEEP_SPECIAL
    METAL_ORE
    THREAD_METAL
    DEEP_SURFACE
    AQUIFER
    METAMORPHIC
    SEDIMENTARY
    SOIL
    SOIL_OCEAN
    SOIL_SAND
    SEDIMENTARY_OCEAN_SHALLOW
    SEDIMENTARY_OCEAN_DEEP
    IGNEOUS_INTRUSIVE
    IGNEOUS_EXTRUSIVE
    ENVIRONMENT
    ENVIRONMENT_SPEC
    USE_MATERIAL_TEMPLATE
    LAVA """.split())

# same as above, but cat plant*
PLANT_TOKENS = set("""
    ALL_NAMES
    ALT_GRASS_TILES
    ALT_PERIOD
    AUTUMN
    AUTUMNCOLOR
    BASIC_MAT
    CLUSTERSIZE
    DEAD_PICKED_COLOR
    DEAD_PICKED_TILE
    DEAD_SAPLING_COLOR
    DEAD_SAPLING_TILE
    DEAD_SHRUB_COLOR
    DEAD_SHRUB_TILE
    DEAD_TREE_COLOR
    DEAD_TREE_TILE
    DRINK
    DRY
    EXTRACT_BARREL
    EXTRACT_STILL_VIAL
    EXTRACT_VIAL
    GRASS
    GRASS_COLORS
    GRASS_TILES
    GROWDUR
    LEAVES
    MILL
    NAME_PLURAL
    PICKED_COLOR
    PICKED_TILE
    SAPLING
    SAPLING_COLOR
    SAPLING_TILE
    SEED
    SHRUB_COLOR
    SHRUB_TILE
    SPRING
    SUMMER
    THREAD
    TREE
    TREE_COLOR
    TREE_TILE
    USE_MATERIAL_TEMPLATE
    WET
    WINTER
    """.split())

#
# cat tissue_template_default.txt | egrep '^[[:space:]]*\[' | 
# grep -v MATERIAL_TEMPLATE | cut -d\[ -f 2| cut -d: -f 1 | cut -d\] -f 1 |sort -u >ttt
#
TISSUE_TEMPLATE_TOKENS = set("""
    ARTERIES
    CONNECTIVE_TISSUE_ANCHOR
    CONNECTS
    COSMETIC
    FUNCTIONAL
    HEALING_RATE
    INSULATION
    MUSCULAR
    OBJECT
    PAIN_RECEPTORS
    RELATIVE_THICKNESS
    SCARS
    SETTABLE
    SPLINTABLE
    STRUCTURAL
    STYLEABLE
    SUBORDINATE_TO_TISSUE
    THICKENS_ON_ENERGY_STORAGE
    THICKENS_ON_STRENGTH
    TISSUE_MATERIAL
    TISSUE_MAT_STATE
    TISSUE_NAME
    TISSUE_SHAPE
    TISSUE_TEMPLATE
    VASCULAR
""".split())

# found in both plants and creatures
PLANT_CREATURE_TOKENS = set("""
    EVIL
    SAVAGE
    GOOD
    BIOME
    PREFSTRING
    VALUE
    ADJ
    NAME
    UNDERGROUND_DEPTH
    FREQUENCY
""".split())

# for the time being
PLANT_TOKENS.update(PLANT_CREATURE_TOKENS)
MATERIAL_TOKENS.update(SYNDROME_TOKENS)
MATERIAL_TOKENS.update(MATERIAL_TEMPLATE_TOKENS)
INORGANIC_TOKENS.update(MATERIAL_TOKENS)
#
# from future import creatures
#


