#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
PERSISTENCE.PY - MODULE DE GESTION DE PERSISTANCE DES DONNÉES
=============================================================================

Description :
    Ce module gère la persistance des données du bot Discord de suivi League
    of Legends. Il fournit une interface simple pour stocker et récupérer les
    informations des joueurs dans un fichier JSON local.

Fonctionnalités principales :
    ✓ Sauvegarde automatique en JSON avec encodage UTF-8
    ✓ Gestion des erreurs et cas d'exception
    ✓ Identification unique des joueurs par PUUID
    ✓ Opérations CRUD (Create, Read, Update, Delete)
    ✓ Structure de données robuste

Architecture des données :
    Les joueurs sont stockés sous forme de liste de dictionnaires contenant :
    - puuid : Identifiant unique Riot Games
    - summoner_name : Nom d'invocateur
    - tag_line : Tag de l'invocateur
    - discord_id : ID Discord de l'utilisateur
    - lp : Points de classement actuels
    - rank : Rang actuel (BRONZE, SILVER, GOLD, etc.)
    - tier : Division (I, II, III, IV)
    - wins : Nombre de victoires
    - losses : Nombre de défaites
    - last_updated : Timestamp de dernière mise à jour

Auteur : Samuel
Date de création : 2025
Dernière modification : 2025
Version : 1.0.0

=============================================================================
"""

# =============================================================================
# IMPORTATION DES MODULES
# =============================================================================

import json
import os
from supabase import create_client, Client

# =============================================================================
# CONFIGURATION GLOBALE
# =============================================================================

# Variable d'environnement
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "tracker-data"
FILE_NAME = "bot_data.json"


# Initialisation du client Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Nom du fichier de données JSON pour la persistance
DATA_FILE = "bot_data.json"

# =============================================================================
# FONCTIONS DE CHARGEMENT DES DONNÉES
# =============================================================================

def load_data():
    """
    Charge les données des joueurs depuis le fichier JSON.
    
    Cette fonction lit le fichier de données JSON et retourne la liste des
    joueurs. Elle gère automatiquement les cas d'erreur comme un fichier
    inexistant ou corrompu.
    
    Gestion des erreurs :
        - Fichier inexistant : retourne une liste vide
        - Fichier corrompu ou format invalide : retourne une liste vide
        - Permissions insuffisantes : retourne une liste vide
    
    Returns:
        list: Liste des dictionnaires contenant les données des joueurs.
              Chaque dictionnaire représente un joueur avec ses statistiques.
              Retourne [] si aucune donnée n'est disponible.
    
    Exemple de structure retournée :
        [
            {
                "puuid": "ABC123...",
                "summoner_name": "PlayerOne",
                "tag_line": "EUW",
                "discord_id": "123456789",
                "lp": 1847,
                "rank": "GOLD",
                "tier": "II",
                "wins": 45,
                "losses": 38,
                "last_updated": "2024-01-15 10:30:00"
            }
        ]
    """
    try:
        response = supabase.storage.from_(BUCKET_NAME).download(FILE_NAME)
        if not response:
            print("Aucune donnée trouvée, initialisation.")
            return {"players": []}
        return json.loads(response.decode("utf-8"))
    except Exception as e:
        print(f"Erreur lors du chargement des données : {e}")
        return {"players": []}

# =============================================================================
# FONCTIONS DE SAUVEGARDE DES DONNÉES
# =============================================================================

def save_data(players_list):
    """
    Sauvegarde la liste des joueurs dans le fichier JSON.
    
    Cette fonction écrit la liste complète des joueurs dans le fichier de
    persistance avec un formatage lisible et un encodage UTF-8 pour supporter
    les caractères spéciaux dans les noms d'invocateurs.
    
    Caractéristiques de la sauvegarde :
        - Formatage JSON indenté (4 espaces) pour la lisibilité
        - Encodage UTF-8 pour supporter les caractères internationaux
        - ensure_ascii=False pour préserver les caractères non-ASCII
        - Écrasement complet du fichier à chaque sauvegarde
    
    Args:
        players_list (list): Liste des dictionnaires représentant les joueurs.
                           Chaque dictionnaire doit contenir les clés requises
                           comme puuid, summoner_name, discord_id, etc.
    
    Raises:
        IOError: Si l'écriture du fichier échoue (permissions, espace disque)
        ValueError: Si players_list n'est pas sérialisable en JSON
    
    Exemple d'usage :
        >>> players = load_data()
        >>> players.append({"puuid": "ABC", "summoner_name": "Test"})
        >>> save_data(players)  # Sauvegarde automatique
    """
    try:
        json_data = json.dumps({"players": players_list}, indent=2)
        supabase.storage.from_(BUCKET_NAME).upload(
            FILE_NAME, json_data.encode("utf-8"), {"upsert": "true"}
        )
        print("Données sauvegardées avec succès sur Supabase.")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des données : {e}")

# =============================================================================
# FONCTIONS DE GESTION DES JOUEURS
# =============================================================================

def add_player(player, players_list):
    """
    Ajoute un nouveau joueur à la liste s'il n'existe pas déjà.
    
    Cette fonction vérifie l'unicité du joueur basée sur le PUUID (identifiant
    unique de Riot Games) avant de l'ajouter. Si le joueur existe déjà, 
    aucune action n'est effectuée pour éviter les doublons.
    
    Processus d'ajout :
        1. Vérification de l'existence par PUUID
        2. Ajout à la liste si nouveau
        3. Sauvegarde automatique des données
        4. Retour du statut de l'opération
    
    Args:
        player (dict): Dictionnaire contenant les données du joueur à ajouter.
                      Doit contenir au minimum la clé "puuid".
        players_list (list): Liste des joueurs existants dans laquelle ajouter.
    
    Returns:
        bool: True si le joueur a été ajouté avec succès.
              False si le joueur existait déjà (basé sur le PUUID).
    
    Structure attendue du dictionnaire player :
        {
            "puuid": "ABC123...",           # Obligatoire - ID unique Riot
            "summoner_name": "PlayerOne",   # Nom d'invocateur
            "tag_line": "EUW",              # Tag de région
            "discord_id": "123456789",      # ID Discord de l'utilisateur
            "lp": 1500,                     # Points de classement
            "rank": "GOLD",                 # Rang actuel
            "tier": "III",                  # Division
            "wins": 50,                     # Victoires
            "losses": 45,                   # Défaites
            "last_updated": "timestamp"     # Dernière mise à jour
        }
    
    Exemple d'usage :
        >>> players = load_data()
        >>> new_player = {"puuid": "ABC123", "summoner_name": "TestPlayer"}
        >>> if add_player(new_player, players):
        ...     print("Joueur ajouté avec succès!")
        ... else:
        ...     print("Joueur déjà existant.")
    """
    # Vérification de l'existence du joueur par PUUID
    for p in players_list:
        if p["puuid"] == player["puuid"]:
            return False
    
    # Ajout du nouveau joueur et sauvegarde
    players_list.append(player)
    save_data(players_list)
    return True

def update_player(player, players_list):
    """
    Met à jour les données d'un joueur existant dans la liste.
    
    Cette fonction recherche un joueur par son PUUID et met à jour toutes ses
    informations avec les nouvelles données fournies. La sauvegarde est 
    automatiquement effectuée après la mise à jour.
    
    Processus de mise à jour :
        1. Recherche du joueur par PUUID dans la liste
        2. Remplacement complet des données du joueur trouvé
        3. Sauvegarde automatique des modifications
        4. Retour du statut de l'opération
    
    Args:
        player (dict): Dictionnaire contenant les nouvelles données du joueur.
                      Doit contenir la clé "puuid" pour l'identification.
        players_list (list): Liste des joueurs dans laquelle effectuer la recherche.
    
    Returns:
        bool: True si le joueur a été trouvé et mis à jour avec succès.
              False si aucun joueur avec ce PUUID n'a été trouvé.
    
    Note importante :
        Cette fonction effectue un remplacement complet des données du joueur.
        Toutes les clés du dictionnaire player vont écraser les données existantes.
        Assurez-vous d'inclure toutes les informations nécessaires.
    
    Exemple d'usage :
        >>> players = load_data()
        >>> updated_player = {
        ...     "puuid": "ABC123",
        ...     "summoner_name": "NewName",
        ...     "lp": 1600,
        ...     "rank": "PLATINUM",
        ...     "wins": 55,
        ...     "losses": 42
        ... }
        >>> if update_player(updated_player, players):
        ...     print("Joueur mis à jour!")
        ... else:
        ...     print("Joueur introuvable.")
    
    Cas d'usage typiques :
        - Mise à jour des LP après une partie
        - Changement de nom d'invocateur
        - Mise à jour des statistiques de rang
        - Actualisation du timestamp de dernière mise à jour
    """
    # Recherche et mise à jour du joueur par PUUID
    for i, p in enumerate(players_list):
        if p["puuid"] == player["puuid"]:
            players_list[i] = player
            save_data(players_list)
            return True
    return False
