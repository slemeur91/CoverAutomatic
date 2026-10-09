<p align="center">
  <img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/custom_components/cover_automatic/brand/logo@2x.png" alt="Logo CoverAutomatic" width="331">
</p>

<h1 align="center">CoverAutomatic V2</h1>

<p align="center"><strong>Intégration personnalisée pour Home Assistant : pilotage intelligent et automatique des volets (volets roulants, stores, brise-soleil, fenêtres de toit).</strong></p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistant&logoColor=white" alt="HACS Custom"></a>
  <a href="https://github.com/slemeur91/CoverAutomatic/releases/latest"><img src="https://img.shields.io/github/v/release/slemeur91/CoverAutomatic?label=Version" alt="Dernière version"></a>
  <a href="https://github.com/slemeur91/CoverAutomatic/actions/workflows/ci.yml"><img src="https://github.com/slemeur91/CoverAutomatic/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/LICENSE"><img src="https://img.shields.io/github/license/slemeur91/CoverAutomatic" alt="Licence"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.3%2B-03a9f4?logo=homeassistant&logoColor=white" alt="Home Assistant 2026.3+">
</p>

<p align="center">🇬🇧 <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/README_EN.md">English version</a> · 📖 <a href="https://github.com/slemeur91/CoverAutomatic/wiki">Wiki</a></p>

---

> **ℹ️ Ceci est un fork**
>
> Ce dépôt est un **fork** du projet [CoverAutomatic de @crandler](https://github.com/crandler/CoverAutomatic).
> Il est basé sur la version d'origine **1.62.1** et ajoute de nombreuses évolutions regroupées dans la **V2**
> (voir [Nouveautés de la V2](#nouveautés-de-la-v2)).
> Pour la version d'origine, sa documentation en anglais et son suivi des anomalies, rendez-vous sur le dépôt d'origine.
> Pour cette V2, utilisez ce dépôt : [github.com/slemeur91/CoverAutomatic](https://github.com/slemeur91/CoverAutomatic).

---

## Avertissement

**AUCUNE GARANTIE – AUCUNE RESPONSABILITÉ**

Ce logiciel est fourni « tel quel », sans garantie d'aucune sorte, explicite ou implicite, notamment sans garantie de qualité marchande, d'adéquation à un usage particulier ou d'absence de contrefaçon.

En aucun cas les auteurs ne pourront être tenus responsables de toute réclamation, de tout dommage ou de toute autre responsabilité, que ce soit dans le cadre d'un contrat, d'un délit ou autre, découlant du logiciel, de son utilisation ou de toute autre manipulation.

**En utilisant ce logiciel, vous reconnaissez que :**
- une mauvaise position des volets peut affecter la sécurité ou le confort thermique de votre logement ;
- vous êtes seul responsable du test et de la validation de son comportement ;
- les auteurs déclinent toute responsabilité en cas de dommage aux biens ou aux équipements.

---

## Fonctionnalités

- **Automatisation selon le soleil** – occultation automatique quand le soleil atteint une façade
- **Prise en compte des températures** – intérieure et extérieure, avec des consignes de confort par pièce
- **Air extérieur comparé à la pièce** – pour aérer quand il fait plus frais dehors ou se protéger de la chaleur
- **Présence** – condition « pièce occupée » selon un capteur de présence par volet
- **Météo** – réaction aux conditions (ensoleillé, nuageux, pluie, orage…)
- **Horaires** – ouverture / fermeture à heure fixe ou par rapport au lever / coucher du soleil, à l'aube ou au crépuscule
- **Règles avancées** – conditions sur n'importe quelle entité (conditions Home Assistant), conditions inversées (NON),
  groupes ET / OU, priorités
- **Règle de sécurité** – agit même en pause, en manuel, en protection vent ou automatisation coupée (alarme incendie…)
- **Scénarios** – bascule entre des modes comme « Quotidien », « Été », « Vacances » ; chaque règle choisit ses scénarios
- **Commande manuelle respectée** – pause automatique après une manœuvre manuelle, reprise à la fin de la pause ou dès que
  le volet revient à la position demandée par sa règle
- **Durée de course du volet** – apprise automatiquement, pour une détection fiable des manœuvres manuelles
- **Fenêtre ouverte** – le volet va à sa position de verrouillage ou garde sa position actuelle ; l'automatisation est
  bloquée tant que la fenêtre est ouverte
- **Fenêtre entrouverte (oscillo-battant)** – position minimale d'aération, l'automatisation continue au-dessus
- **Protection contre le vent** – position de repli réglable au-delà d'un seuil de vent
- **Heures d'arrivée / de départ du soleil** – pour chaque façade, calculées sur la vraie course du soleil
- **Hystérésis** – limite l'usure des moteurs (écart minimal de position et délai minimal entre deux mouvements)
- **Volets inversés** – pris en charge (100 % = fermé)
- **Carte de tableau de bord et capteurs** – suivi de chaque volet (règle active, position cible, fin de pause) et des
  volets en pause, en manuel ou verrouillés
- **Journal d'activité** – historique des mouvements et des changements de statut, filtrable par volet
- **Sauvegarde / restauration** – de toute la configuration, depuis le panneau ou par service
- **Configuration entièrement graphique** – tout se fait dans l'interface de Home Assistant, sans YAML
- **Indépendant du matériel** – fonctionne avec toute entité `cover` (Somfy, Velux, Shelly, Zigbee, Z-Wave…)

---

## Nouveautés de la V2

La V2 regroupe toutes les évolutions apportées depuis la version d'origine 1.61.1.

### Langue française
- Toute l'intégration est traduite : panneau de configuration, carte de tableau de bord, services et messages d'erreur,
  journal d'activité et journal de Home Assistant, entités, appareils de façade, états météo et scénarios intégrés (« Quotidien »…).
- La langue suivie est celle de Home Assistant, avec la typographie française (espace fine avant « : »).

### Règles
- **Conditions Home Assistant** : n'importe quelle condition d'automatisation (état, valeur numérique, template, zone, soleil…),
  saisie par formulaire ou en YAML, vérifiée en direct (voir [plus bas](#conditions-sur-nimporte-quelle-entité-conditions-home-assistant)).
- **Groupes de conditions et NON** : par exemple (A OU B) ET (C OU D). Une condition inversée par NON n'est jamais remplie
  tant que son capteur est indisponible, pour éviter un mouvement intempestif.
- **Scénarios par règle** : chaque règle choisit les scénarios dans lesquels elle s'applique.
- **Aube et crépuscule** (crépuscule civil), avec un décalage en minutes. Les paires « après le lever / avant le coucher »
  et « après l'aube / avant le crépuscule » sont complémentaires : pas de trou ni de chevauchement, même avec des décalages.
- **Air extérieur comparé à la pièce** : « air extérieur plus frais / plus chaud que la pièce », avec un écart minimal.
  Idéal pour aérer ou protéger de la chaleur ; une seule règle sert à toutes les pièces.
- **Pièce occupée** : un capteur de présence par volet (capteur binaire, personne, sélecteur…) et la condition « Pièce occupée »
  (avec NON : « pièce libre »).
- **Règle de sécurité** : elle agit même si le volet est en pause, en mode manuel, en protection vent ou avec l'automatisation coupée.
  Elle ne passe jamais outre le verrouillage d'une fenêtre ouverte et, entre règles, c'est la priorité qui décide.
  Exemple d'usage : l'alarme incendie.
- **Dupliquer une règle** : la copie est créée juste sous l'original. Boutons ▲▼ pour ordonner les conditions, les groupes
  et les priorités (clavier et tactile).

### Volets
- **Garder la position quand la fenêtre s'ouvre** : nouveau choix en plus de la position de verrouillage. À l'ouverture de la
  fenêtre, le volet peut soit aller à sa position de verrouillage (comportement d'origine), soit rester où il est ; dans les
  deux cas, l'automatisation est bloquée tant que la fenêtre reste ouverte.
- **Durée de course du volet** : saisie ou apprise automatiquement, avec une valeur par défaut globale. Elle évite les fausses pauses
  « manuelles » sur les volets lents qui n'indiquent pas leur position pendant le mouvement.
- **Reprise quand la position correspond à la règle** : une pause due à une manœuvre manuelle se termine dès que le volet
  revient à la position demandée par sa règle (remis en place à la main, ou la règle a changé entre-temps).
- **Commandes perdues renvoyées** : une commande que le volet n'a pas exécutée (trame radio perdue) est renvoyée,
  jamais après un contre-ordre manuel.

### Réglages
- **Position de protection contre le vent** réglable (au lieu de toujours ouvrir complètement).
- **Seuils pilotés par une entité** : les consignes de température et le seuil d'ensoleillement peuvent suivre une entité
  (`input_number`, capteur…), avec repli sur la valeur saisie.
- **Comportement « soleil sur la façade »** configurable, globalement puis volet par volet (pièce froide, pièce dans la
  plage de confort, fort ensoleillement).
- **Couleurs des températures** au choix : selon l'action à mener ou façon thermomètre.
- Réglages réorganisés (Maison, Capteurs, Exposition au soleil, Vent, Automatisation, Sauvegarde) avec des blocs
  « Comment ça marche ? » et des options grisées quand elles sont sans effet.

### Entités et tableau de bord
- **Carte de tableau de bord** `custom:cover-automatic-card` (nouvelle carte, en plus du panneau, qui ne change rien
  au fonctionnement existant) : une ligne par volet (position, règle active, statut, temps de
  pause restant, bouton de reprise, interrupteur d'automatisation) et un en-tête global (scénario, interrupteur général, vent,
  nombre de volets en pause / manuels / verrouillés, bouton « Tout reprendre »).
- **Capteurs par volet** (nouveaux, en plus de l'interrupteur et du statut existants) : règle active, position cible, position,
  mode confort, fin de pause (voir [Entités créées](#entités-créées)).
- **Entités globales** : protection contre le vent et nombre de volets en pause, en manuel ou verrouillés.
- Les appareils et entités sont créés et supprimés automatiquement quand on ajoute ou supprime un volet ou une façade.

### Interface
- **Fiche volet** en sections repliables : Général, Fenêtre, Pièce, Exposition au soleil, Automatisation.
- **Éditeur de règles** : conditions repliables, brouillon conservé, avertissement avant de perdre des modifications.
- **Onglet Scénarios** : règles listées par priorité, règles désactivées grisées, badge « Sécurité ».
- **Journal** filtrable par volet, avec un bouton depuis la fiche du volet.
- **Mobile** : en-tête de la fiche accessible sous l'encoche, libellés courts, défilement et saisie conservés.

### Fiabilité et sécurité
- **Fenêtre et vent** : le verrouillage d'une fenêtre ouverte reste prioritaire sur le vent pendant toute la tempête ;
  les états verrouillé / vent survivent à un redémarrage ; un capteur de fenêtre inconnu n'abaisse jamais le volet ;
  un capteur supprimé ne bloque plus le volet indéfiniment.
- **Fausses pauses manuelles supprimées** : volets lents, changement de règle pendant un mouvement, fenêtre refermée
  pendant que le volet rejoint sa position de verrouillage.
- **Sauvegardes** : export complet, import vérifié (valeurs aberrantes, références inconnues, migrations) ; l'état
  d'exécution n'est plus restauré depuis le fichier.
- Trois audits complets du code et plus de 1 300 tests automatisés.

---

## Captures d'écran

L'intégration ajoute un panneau dans la barre latérale de Home Assistant. Toute la configuration s'y fait, sans YAML.
Cliquez sur une vignette pour l'agrandir.

<table>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/covers-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/covers-desktop.png" alt="Volets" /></a>
      <p align="center"><sub><b>Volets</b> – liste, statut, température, position, règle active</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/facades-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/facades-desktop.png" alt="Façades" /></a>
      <p align="center"><sub><b>Façades</b> – azimuts et volets associés</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/scenarios-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/scenarios-desktop.png" alt="Scénarios" /></a>
      <p align="center"><sub><b>Scénarios</b> – règles par scénario, badge Sécurité</sub></p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/rule-editor.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/rule-editor.png" alt="Éditeur de règle" /></a>
      <p align="center"><sub><b>Éditeur de règle</b> – scénarios, volets, conditions</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/settings-house.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/settings-house.png" alt="Paramètres – Maison" /></a>
      <p align="center"><sub><b>Paramètres – Maison</b> – rotation et secteur ensoleillé</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/settings-automation.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/settings-automation.png" alt="Paramètres – Automatisation" /></a>
      <p align="center"><sub><b>Paramètres – Automatisation</b> – valeurs par défaut globales</sub></p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/settings-sensors.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/settings-sensors.png" alt="Paramètres – Capteurs" /></a>
      <p align="center"><sub><b>Paramètres – Capteurs</b> – consignes de température</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/log-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/log-desktop.png" alt="Journal" /></a>
      <p align="center"><sub><b>Journal</b> – mouvements et changements de statut</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/cover-editor.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/cover-editor.png" alt="Fiche volet" /></a>
      <p align="center"><sub><b>Fiche volet</b> – panneau latéral par sections</sub></p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/rules-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/rules-desktop.png" alt="Règles" /></a>
      <p align="center"><sub><b>Règles</b> – filtre, priorités, badge Sécurité, conditions</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/settings-sun.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/settings-sun.png" alt="Paramètres – Exposition au soleil" /></a>
      <p align="center"><sub><b>Paramètres – Exposition au soleil</b> – comportement de « Soleil sur la façade »</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/settings-wind.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/settings-wind.png" alt="Paramètres – Protection contre le vent" /></a>
      <p align="center"><sub><b>Paramètres – Protection contre le vent</b> – seuil, hystérésis, position</sub></p>
    </td>
  </tr>
</table>

<table>
  <tr>
    <td width="33%" align="center">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/card.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/card.png" alt="Carte de tableau de bord" width="320" /></a>
      <p><sub><b>Carte de tableau de bord</b> – position, règle active, température, statut</sub></p>
    </td>
    <td width="33%" align="center">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/mobile-covers.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/mobile-covers.png" alt="Mobile – Volets" width="320" /></a>
      <p><sub><b>Mobile – Volets</b></sub></p>
    </td>
    <td width="33%" align="center">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/fr/mobile-settings.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/fr/mobile-settings.png" alt="Mobile – Paramètres" width="320" /></a>
      <p><sub><b>Mobile – Paramètres</b> – sections en barre horizontale</sub></p>
    </td>
  </tr>
</table>

## Prérequis

- Home Assistant 2026.3.0 ou plus récent
- HACS (Home Assistant Community Store) pour l'installation via HACS
- Des entités `cover` existantes à piloter

---

## Installation

> Si la version d'origine de @crandler est déjà installée, supprimez-la (ou remplacez son dossier) avant d'installer cette V2 :
> les deux utilisent le même dossier `cover_automatic`. Votre configuration (volets, façades, règles) est conservée.

### Méthode 1 : HACS (recommandée)

[![Ouvrir votre Home Assistant et ajouter ce dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=slemeur91&repository=CoverAutomatic&category=integration)

#### Étape 1 : ajouter le dépôt personnalisé

1. Ouvrez Home Assistant
2. Allez dans **HACS** dans la barre latérale
3. Cliquez sur le **menu à trois points** (en haut à droite)
4. Choisissez **Dépôts personnalisés**
5. Dans la fenêtre :
   - **Dépôt :** `https://github.com/slemeur91/CoverAutomatic`
   - **Type :** `Intégration`
6. Cliquez sur **Ajouter**

#### Étape 2 : installer l'intégration

1. Dans HACS, recherchez **CoverAutomatic**
2. Ouvrez-la puis cliquez sur **Télécharger**
3. Choisissez la dernière version et confirmez

#### Étape 3 : redémarrer Home Assistant

1. **Paramètres** > **Système** > **Redémarrer**
2. Attendez que Home Assistant redémarre

#### Étape 4 : ajouter l'intégration

1. **Paramètres** > **Appareils et services**
2. Cliquez sur **+ Ajouter une intégration** (en bas à droite)
3. Recherchez **CoverAutomatic**
4. Confirmez (aucune saisie nécessaire)
5. Une entrée **CoverAutomatic** apparaît dans la barre latérale pour toute la configuration

---

### Méthode 2 : installation manuelle

1. Téléchargez la dernière version depuis [github.com/slemeur91/CoverAutomatic](https://github.com/slemeur91/CoverAutomatic)
   (bouton **Code** > **Download ZIP**, ou la page des [versions](https://github.com/slemeur91/CoverAutomatic/releases))
2. Supprimez l'ancien dossier `config/custom_components/cover_automatic` s'il existe
3. Copiez le dossier `custom_components/cover_automatic` dans le répertoire `config/custom_components/` de Home Assistant
4. Redémarrez Home Assistant
5. Ajoutez l'intégration via **Paramètres** > **Appareils et services** > **Ajouter une intégration**

Après une mise à jour, rechargez la page du navigateur (Ctrl/Cmd+Maj+R) pour charger le nouveau panneau.

---

## Configuration

Après l'installation, tout se configure dans le panneau **CoverAutomatic** de la barre latérale.
Le [wiki](https://github.com/slemeur91/CoverAutomatic/wiki) détaille chaque partie de l'intégration, avec des captures d'écran.

1. **Volets** – ajoutez les entités `cover` à piloter ; chaque volet a sa fiche (fenêtre, pièce, exposition, automatisation)
2. **Façades** – définissez les façades du bâtiment par orientation. Pour une
   nouvelle façade, les azimuts de début et de fin sont préremplis avec l'ouverture maximale de l'orientation choisie
   (90° de chaque côté, rotation de la maison appliquée, sans le secteur où le soleil ne passe jamais à votre
   latitude) et restent modifiables
3. **Règles** – créez les règles d'automatisation à partir de conditions (soleil, température, heure, météo, entités…).
   La liste se filtre par façade, volet et scénario.
   Les conditions peuvent être inversées (NON) et organisées en groupes, par exemple (A OU B) ET (C OU D) ;
   une règle existante peut être dupliquée comme point de départ
4. **Scénarios** – définissez des modes comme « Quotidien », « Été », « Vacances ». Chaque règle choisit ses scénarios
   (tous par défaut) ; dans un scénario, une règle peut aussi être désactivée temporairement
5. **Paramètres** – capteurs, consignes de température, exposition au soleil, protection contre le vent, sauvegarde…
6. **Journal** – historique des mouvements et changements de statut, filtrable par volet et par type

### Fiche d'un volet

Un clic sur un volet de l'onglet **Volets** ouvre sa fiche, organisée en sections repliables. Un champ laissé vide
reprend la valeur par défaut des **Paramètres**.

| Section | Contenu |
|---------|---------|
| **Général** | Automatisation activée, façade, inverser le sens ouverture/fermeture, inclinaison inversée |
| **Fenêtre** | *Fenêtre ouverte* : capteur, **garder la position actuelle** ou aller à la position de verrouillage (et son inclinaison). *Fenêtre basculée* : capteur, position d'aération (et son inclinaison) |
| **Pièce** | Capteur de température intérieure et consignes froide / chaude (nombre ou entité), capteur d'occupation et états « pièce occupée » |
| **Exposition au soleil** | Réglages « soleil sur la façade » propres à ce volet (ou réglage global) |
| **Automatisation** | Durée de pause, reprise quand la position correspond à la règle, écart minimal de position, délai minimal entre changements, **durée de course du volet** (saisie ou mesurée) |

Le bouton « Voir le journal de ce volet » ouvre le journal filtré sur ce volet.

### Paramètres

| Onglet | Contenu |
|--------|---------|
| **Maison** | Rotation de la maison, avec boussole (Sud en haut ; position du soleil, secteur ensoleillé aux couleurs des quatre côtés de la maison, avec leurs azimuts en légende) ; choix de faire pivoter ou non les façades existantes quand la rotation change |
| **Capteurs** | Capteur de température intérieure global et consignes froide / chaude avec leur hystérésis ; capteur de température extérieure et hystérésis utilisée par les règles ; météo ; jour ouvré |
| **Exposition au soleil** | Comportement de « Soleil sur la façade » selon la température de la pièce ; capteur d'ensoleillement, seuil de fort ensoleillement et hystérésis |
| **Protection contre le vent** | Capteur de vent, seuil, hystérésis et **position de protection** |
| **Automatisation** | *Pause après une commande manuelle* (durée, reprise quand la position correspond à la règle) ; *Positions de fenêtre* par défaut ; *Mouvements* (écart minimal, délai minimal, délai entre commandes, durée de course par défaut) ; *Journal et mises à jour* |
| **Sauvegarde** | Export / import de toute la configuration (fichier JSON) |

Les consignes de température et le seuil d'ensoleillement peuvent suivre une **entité** (`input_number`, capteur…) :
sa valeur est alors utilisée, le nombre saisi servant de secours si l'entité est indisponible.

### Conditions disponibles

Le menu *Ajouter une condition* les regroupe par thème (✨ = nouveau dans la V2) :

| Groupe | Conditions |
|--------|------------|
| **Soleil** | Soleil sur la façade ; élévation solaire supérieure / inférieure à |
| **Température** | Température extérieure supérieure / inférieure à ; température de la pièce (froide, entre les consignes, chaude) ; ✨ air extérieur comparé à la pièce (plus frais / plus chaud, écart minimal) |
| **Présence** | ✨ Pièce occupée (selon le capteur d'occupation du volet) |
| **Horaires** | Heure comprise entre ; avant / après le lever du soleil ; avant / après le coucher du soleil ; ✨ avant / après l'aube ; ✨ avant / après le crépuscule (avec décalage en minutes) ; jour de la semaine ; jour ouvré |
| **Météo** | La météo est (tous les états météo de Home Assistant) |
| **Entités** | ✨ État d'une entité ; ✨ valeur numérique d'une entité ; ✨ condition Home Assistant (YAML) |

Chaque condition peut être inversée avec **NON** ; une condition inversée n'est jamais remplie tant que la valeur qu'elle lit
est indisponible. Les conditions se répartissent en **groupes** : chaque groupe a son opérateur (ET / OU) et les groupes
sont reliés par un autre opérateur, par exemple (A OU B) ET (C OU D).

### Règle de sécurité

Dans l'éditeur, la case **Règle de sécurité** fait agir la règle même quand le volet est en pause après un mouvement manuel,
en mode manuel, en protection contre le vent ou quand l'automatisation (du volet ou générale) est coupée. La prise en main
et sa fin sont écrites dans le journal. Une règle de sécurité ne passe jamais outre le verrouillage d'une fenêtre ouverte et,
entre plusieurs règles, c'est toujours la priorité qui décide : placez-la en haut de la liste. À réserver aux urgences,
par exemple l'alarme incendie.

### Exemple : protection contre la chaleur selon la température extérieure

Pour occulter une façade quand il fait chaud dehors, combinez deux conditions dans une règle (opérateur **ET**).
Aucun réglage supplémentaire : la condition « Température extérieure supérieure à » lit par défaut le capteur de température
extérieure défini dans les **Paramètres**.

1. Choisissez un **capteur de température extérieure** dans les Paramètres.
2. Créez une règle, par exemple *« Protection chaleur Sud »* :
   - condition « Soleil sur la façade » → votre façade sud
   - condition « Température extérieure supérieure à » → `28` (°C)
   - position cible → par exemple `30` (partiellement fermé)
3. Facultatif : donnez-lui une priorité plus haute que votre règle de jour habituelle pour qu'elle l'emporte
   quand le soleil est sur la façade et qu'il fait chaud.

La règle ferme le volet uniquement quand le soleil frappe réellement la façade **et** que la température extérieure
dépasse le seuil, puis le libère dès que l'une des deux conditions n'est plus remplie.

### Conditions sur n'importe quelle entité (conditions Home Assistant)

Le groupe **Entités** du menu *Ajouter une condition* ajoute une condition évaluée par Home Assistant lui-même,
au même format que la section `condition:` d'une automatisation :

- **État d'une entité** / **Valeur numérique d'une entité** ouvrent un formulaire : choisissez l'entité,
  éventuellement un attribut, puis les états (proposés sous forme de boutons, par exemple les zones d'une personne),
  *est / n'est pas*, une durée minimale, ou supérieur / inférieur / entre.
- **Condition Home Assistant (YAML)** accepte n'importe quelle condition d'automatisation —
  templates, zones, appareils, `and` / `or` / `not` imbriqués :

```yaml
condition: or
conditions:
  - condition: state
    entity_id: media_player.salon
    state: [playing, paused]
  - condition: template
    value_template: "{{ states('sensor.luminosite') | float(0) > 20000 }}"
```

Chaque condition a un bouton **Formulaire / YAML**, est vérifiée par Home Assistant pendant la saisie et affiche les
entités qu'elle surveille (les règles réagissent immédiatement à leurs changements). Une condition invalide ou
incomplète est conservée mais n'est jamais remplie, et elle est signalée en rouge.

### Entités créées

Pour chaque volet géré, un appareil « CoverAutomatic *nom du volet* » regroupe :

| Entité | Description |
|--------|-------------|
| `switch` Automatisation | Active / désactive l'automatisation du volet |
| `sensor` Statut | Statut actuel (auto / pause / manuel / verrouillé / aération / protection vent). Attributs : `rule_name`, `rule_id` et `target_position` (règle qui commande le volet ; vide en pause, en manuel, verrouillé ou en protection vent, sauf si une règle de sécurité le commande), ainsi que position, fin de pause, règle de sécurité, mode confort, `sun_on_facade` (soleil sur la façade du volet), `room_temp_sensor` (capteur de température de la pièce)… |
| `sensor` Règle active | Nom de la règle qui commande le volet |
| `sensor` Position cible | Position demandée par la règle active (%) |
| `sensor` Position (échelle des règles) | Position actuelle, inversée pour les volets inversés (%) |
| `sensor` Mode confort | Froid / confort / chaud selon la température de la pièce |
| `sensor` Fin de pause | Heure de fin de la pause en cours |

Pour chaque façade, un appareil « CoverAutomatic Façade *nom* » regroupe :

| Entité | Description |
|--------|-------------|
| `sensor` Soleil sur la façade | Oui / Non |
| `sensor` Heure d'arrivée du soleil | Heure à laquelle le soleil atteint la façade aujourd'hui (vraie course du soleil à votre position) |
| `sensor` Heure de départ du soleil | Heure à laquelle le soleil quitte la façade aujourd'hui |

Entités globales (appareil « CoverAutomatic ») :

| Entité | Description |
|--------|-------------|
| `switch` CoverAutomatic | Interrupteur général de l'automatisation. Coupé, le verrouillage fenêtre ouverte, l'aération et les règles de sécurité restent actifs. Attributs : capteurs globaux choisis dans les Paramètres (température extérieure, météo, ensoleillement et son seuil), utilisés par la carte |
| `select` Scénario | Scénario actif (attribut `scenario_names` : noms affichés des scénarios) |
| `binary_sensor` Protection vent | Activée quand le vent dépasse le seuil (attributs : vitesse du vent, seuil, hystérésis) |
| `sensor` Volets en pause / en manuel / verrouillés | Nombre de volets dans ce statut (noms en attributs) |

Les appareils et entités sont créés et supprimés automatiquement quand des volets ou des façades sont ajoutés ou
supprimés dans le panneau ou par un import, sans redémarrage. Un appareil resté orphelin peut être supprimé depuis
sa page d'appareil.

Remarque : l'intégration pilote directement vos entités `cover` d'origine ; elle ne crée pas d'entités `cover` intermédiaires.

### Carte de tableau de bord

La carte `custom:cover-automatic-card` est chargée automatiquement et proposée dans le sélecteur de cartes, avec un éditeur visuel.
Options : `title`, `covers` (tous par défaut), `show_rule`, `show_auto`, `show_temp` (température de la pièce,
avec les couleurs choisies dans les Paramètres), `show_header`.

```yaml
type: custom:cover-automatic-card
title: Volets
show_header: true
```

### Services disponibles

| Service | Description |
|---------|-------------|
| `cover_automatic.pause` | Met en pause l'automatisation d'un volet |
| `cover_automatic.resume` | Reprend l'automatisation d'un volet (équivalent de la croix dans le panneau) |
| `cover_automatic.pause_all` | Met en pause tous les volets |
| `cover_automatic.resume_all` | Reprend tous les volets |
| `cover_automatic.set_scenario` | Choisit le scénario actif |
| `cover_automatic.export_config` | Exporte la configuration dans un fichier YAML |
| `cover_automatic.import_config` | Importe la configuration depuis un fichier YAML |

La sauvegarde et la restauration sont aussi disponibles dans **Paramètres > Sauvegarde** du panneau (fichier JSON).

---

## Dépannage

La plupart des « bugs » sont en fait l'un des mécanismes de sécurité ci-dessous qui fait son travail.
Consultez cette liste avant d'ouvrir un ticket.

### Les volets ne bougent pas juste après un redémarrage de Home Assistant

C'est voulu. Après le démarrage, CoverAutomatic attend **120 secondes** avant d'appliquer des positions.
Ce délai évite de mauvais mouvements tant que les capteurs ne remontent pas encore toutes leurs données
(par exemple une passerelle Zigbee pas encore reconnectée). L'automatisation démarre au premier cycle après ce délai.

### Un volet passe soudain en PAUSE

CoverAutomatic a détecté une **commande manuelle** : le volet a été déplacé par autre chose que CoverAutomatic
(interrupteur mural, télécommande, autre automatisation, interface de Home Assistant). L'automatisation de ce volet
se met en pause pendant la durée configurée (globale ou par volet) pour respecter votre choix, puis reprend toute seule.
Elle reprend aussi dès que le volet revient à la position demandée par sa règle (option « Reprendre quand la position
correspond à la règle »). Pour reprendre plus tôt : la croix dans le panneau, l'interrupteur « Automatisation » du volet
ou le service `cover_automatic.resume`.

Pour les volets lents qui n'indiquent ni positions intermédiaires ni *ouverture* / *fermeture* en cours, l'intégration
attend la **durée de course du volet** (apprise automatiquement, ou saisie dans la fiche du volet, section Automatisation)
avant de considérer une position comme manuelle. Si un volet lent passe encore à tort en pause juste après un mouvement
automatique, saisissez une durée de course du volet un peu supérieure à la réalité.

### Une règle est remplie mais le volet ne bouge pas

Vérifiez dans cet ordre :

1. **Priorité des statuts** — PROTECTION VENT, VERROUILLÉ (fenêtre ouverte), AÉRATION (fenêtre entrouverte) et PAUSE
   passent avant les règles (sauf une règle de sécurité, qui agit aussi en pause, en manuel et en protection vent).
   La liste des volets du panneau affiche le statut et la règle active de chaque volet.
2. **Interrupteur général / automatisation du volet** — les deux doivent être activés.
3. **Scénario actif** — seules les règles du scénario actif (et non désactivées dans ce scénario) sont prises en compte.
4. **Délai minimal entre deux mouvements** — les changements de position sont limités dans le temps ; le mouvement a lieu
   à un cycle suivant.

### Une règle de soleil n'occulte pas

Pour un volet qui a un capteur de température intérieure (le sien ou le capteur global), la condition « Soleil sur la façade »
tient compte de la température de la pièce, selon les réglages de **Paramètres > Exposition au soleil** (modifiables volet par
volet dans la section « Exposition au soleil » de sa fiche) :

- pièce **froide** (au plus la consigne froide) : avec l'option « laisser le soleil chauffer » (activée par défaut), la condition
  répond « pas de soleil » pour laisser le soleil chauffer la pièce ;
- pièce **entre les consignes** : selon le choix « dès que le soleil est sur la façade », « jamais (attendre que la pièce devienne
  trop chaude) » ou « seulement en cas de fort ensoleillement » (capteur d'ensoleillement au-dessus de son seuil) ;
- pièce **chaude** (au moins la consigne chaude) : la condition répond « soleil » dès que le soleil est sur la façade.

Le bloc « Comment ça marche ? » de ces réglages montre le résultat pour vos propres valeurs.

### Un volet reste VERROUILLÉ ou en AÉRATION

Ces statuts viennent des capteurs de fenêtre configurés : verrouillé = fenêtre ouverte (automatisation bloquée),
aération = fenêtre entrouverte (le volet garde une position minimale). Si le capteur lui-même est `unavailable` ou `unknown`,
le dernier statut est conservé par sécurité — vérifiez le capteur plutôt que l'intégration. Un capteur supprimé
de Home Assistant est ignoré après le délai de démarrage (indiqué dans le journal).

### Le panneau semble cassé ou ancien après une mise à jour

Le fichier du panneau est rechargé à chaque version, mais certains navigateurs le gardent en cache.
Forcez le rechargement (Ctrl/Cmd+Maj+R) ou videz le cache de l'application compagnon Home Assistant.

### Activer les journaux de débogage

**Paramètres > Appareils et services > CoverAutomatic** > menu à trois points > **Activer la journalisation de débogage**.
Reproduisez le problème puis désactivez-la de la même façon : Home Assistant propose le journal en téléchargement.
Joignez-le à votre signalement avec une sauvegarde de la configuration (Paramètres > Sauvegarde, ou service
`cover_automatic.export_config`).

Toujours bloqué ? [Signalez une anomalie](https://github.com/slemeur91/CoverAutomatic/issues/new?template=bug_report.yml) —
le formulaire demande tout ce qu'il faut pour vous aider rapidement.

---

## Confidentialité

- **Vérification des mises à jour :** quand le panneau est ouvert, il envoie une requête `GET` anonyme à l'API publique
  de GitHub (`api.github.com`, hébergée aux États-Unis) pour lire le numéro de la dernière version publiée et afficher
  une indication de mise à jour. Aucun compte, jeton ni donnée personnelle n'est envoyé. Cette vérification peut être
  désactivée dans **Paramètres > Automatisation > Vérifier les mises à jour** : aucune requête n'est alors envoyée.
  L'automatisation elle-même ne contacte jamais GitHub.
- **Sauvegardes :** les fichiers exportés contiennent les identifiants de vos capteurs et volets. Des identifiants nommés
  d'après des pièces ou des personnes (par exemple `cover.chambre_anna`) peuvent contenir une référence personnelle.
  Conservez ces fichiers comme toute autre sauvegarde de configuration.

---

## Version

2.0.8

## Historique des versions

L'historique complet est tenu dans le [CHANGELOG.md](https://github.com/slemeur91/CoverAutomatic/blob/main/CHANGELOG.md) (en anglais), au format [Keep a Changelog](https://keepachangelog.com/).

Dernière version : v2.0.8 (2026-10-09), basée sur la version d'origine
[v1.62.1](https://github.com/crandler/CoverAutomatic/releases/tag/v1.62.1) de @crandler.

## Licence

Licence MIT — voir le fichier [LICENSE](https://github.com/slemeur91/CoverAutomatic/blob/main/LICENSE). Le texte de la licence fait foi dans sa version anglaise ci-dessous.

```
MIT License

Copyright (c) 2026 Sven Eulberg
Copyright (c) 2026 slemeur91 (fork CoverAutomatic V2)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Auteurs

- Projet d'origine : [@crandler](https://github.com/crandler) — [github.com/crandler/CoverAutomatic](https://github.com/crandler/CoverAutomatic)
- Fork V2 : [@slemeur91](https://github.com/slemeur91) — [github.com/slemeur91/CoverAutomatic](https://github.com/slemeur91/CoverAutomatic)

**Ce n'est pas un produit officiel.**

---

## Développement

Ce projet a été développé avec l'aide d'une IA (Claude, d'Anthropic) sous supervision humaine.
Chaque modification est relue et validée par une personne avant d'être publiée.

**Assisté par IA | Supervision humaine | Code relu**
