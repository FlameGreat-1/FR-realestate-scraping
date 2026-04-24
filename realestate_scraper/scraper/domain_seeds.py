from urllib.parse import urlparse


DOMAIN_SEEDS = {
    "capwestresidence.fr": [
        "https://www.capwestresidence.fr/destinations?",
    ],
    "cosialis.fr": [
        "https://www.cosialis.fr/annonce/",
    ],
    "zelidom.fr": [
        "https://www.zelidom.fr/annonces?map=1",
        "https://www.zelidom.fr/",
    ],
    "well-estate.fr": [
        "https://www.well-estate.fr/en/",
    ],
    "eraimmobilier.com": [
        "https://www.eraimmobilier.com/acheter",
    ],
    "novilis.fr": [
        "https://www.novilis.fr/acheter",
    ],
    "mylogement.com": [
        "https://mylogement.com/",
    ],
    "guy-hoquet.com": [
        "https://www.guy-hoquet.com/biens/result#1&p=1&f10=1",
    ],
    "bouc-bel-air.guy-hoquet.com": [
        "https://bouc-bel-air.guy-hoquet.com/biens/result#1&p=1&f10=1",
    ],
    "agence-beci.com": [
        "https://www.agence-beci.com/immobilier/vente/tout-type/partout/?lsi_s_extends=0",
    ],
    "laforet.com": [
        "https://www.laforet.com/acheter/rechercher?filter%5Bcities%5D%5B%5D=&filter%5Btypes%5D%5B%5D=house&filter%5Btypes%5D%5B%5D=apartment&filter%5Bmax%5D=",
    ],
    "groupe-tolosan-immobilier.com": [
        "https://www.groupe-tolosan-immobilier.com/",
    ],
    "montpellier-antigone.guy-hoquet.com": [
        "https://montpellier-antigone.guy-hoquet.com/biens/result#1&p=1&f10=1",
    ],
    "a2bimmo.com": [
        "https://www.a2bimmo.com/fr/listing.html?loc=vente&surfacemin=&prixmax=&surfacemax=&prixmin=&piecemin=&chambremin=&terrainmin=&numero=&tri=&page=1&btnSubmit=To+research",
    ],
    "capsud-immo.com": [
        "https://www.capsud-immo.com/immobilier/vente-type/maison-categorie/1p-chambres/",
    ],
    "atlanticviager.fr": [
        "https://www.atlanticviager.fr/annonces/",
    ],
    "galyo.fr": [
        "https://www.galyo.fr/resultat.php",
    ],
    "gardnerimmobilier.com": [
        "https://gardnerimmobilier.com/fr/recherche",
    ],
    "immoso.fr": [
        "https://immoso.fr/en/search",
    ],
    "immograndlyon.com": [
        "https://immograndlyon.com/en/search",
    ],
    "immobiliere-de-croix.com": [
        "https://immobiliere-de-croix.com/#!/annonces-immobilieres-immobiliere-de-croix/",
    ],
    "grisel-immobilier.fr": [
        "https://grisel-immobilier.fr/en/search",
    ],
    "jeminstalleici.com": [
        "https://www.jeminstalleici.com/131-1-208-achete.html?frm_id_type_annonce=1&choix=rechercher_immo_annonce&frm_str_ville_titre=&frm_id_ville=&frm_id_type_bien=0&frm_flt_tarif_min=&frm_flt_tarif_max=&frm_flt_surface_min=&frm_flt_surface_max=&frm_rayon=10&valider=valider&redir=1",
    ],
    "idimmo31.idimmo.net": [
        "https://idimmo31.idimmo.net/vente/",
    ],
    "chatillonestate.com": [
        "https://www.chatillonestate.com/immobilier/vente-type/appartement-categorie/1p-pieces/",
    ],
    "sti-immo.fr": [
        "https://www.sti-immo.fr/annonces/",
    ],
    "pbfimmobilier.fr": [
        "https://www.pbfimmobilier.fr/vente/maison?prod.prod_type=house",
    ],
    "immobiliere-abc.com": [
        "https://immobiliere-abc.com/en/",
    ],
    "vivesimmobilier.fr": [
        "https://www.vivesimmobilier.fr/fr/liste.htm?ope=1#TypeModeListeForm=text&ope=1",
    ],
    "immoboucbelair.com": [
        "https://www.immoboucbelair.com/biens-immobiliers/tous/location",
    ],
    "maisonbianchi.eu": [
        "https://maisonbianchi.eu/en/search",
    ],
    "rhpatrimoine.com": [
        "https://www.rhpatrimoine.com/vente/appartement?prod.prod_type=appt%2Cbuild%2Chouse%2Cland%2Cpark",
    ],
}


def get_additional_seed_urls(base_url: str) -> list[str]:
    hostname = urlparse(base_url).netloc.lower().replace("www.", "")
    seeds = []
    for key, urls in DOMAIN_SEEDS.items():
        if hostname == key or hostname.endswith("." + key) or key.endswith("." + hostname):
            seeds.extend(urls)
    return list(dict.fromkeys(seeds))
