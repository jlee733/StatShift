"""Sample fantasy-football documents for RAG seeding."""

DOCUMENTS = [
    {
        "title": "Christian McCaffrey 2024 rushing workload",
        "category": "player",
        "content": (
            "Christian McCaffrey played 16 games in 2024 with 272 carries for 1,459 rushing yards "
            "and 14 rushing TDs. He added 67 receptions for 564 yards and 7 receiving TDs in PPR leagues. "
            "His 21.8 fantasy PPG ranked RB1 in season-long formats."
        ),
    },
    {
        "title": "Ja'Marr Chase 2024 target share",
        "category": "player",
        "content": (
            "Ja'Marr Chase led the NFL with 175 targets in 2024, a 28.4% team target share. "
            "He posted 127 receptions, 1,708 yards, and 12 TDs. "
            "In PPR scoring he averaged 22.1 fantasy points per game."
        ),
    },
    {
        "title": "Week 12 RB matchup notes",
        "category": "matchup",
        "content": (
            "Week 12 featured several run-heavy game scripts. "
            "Baltimore allowed 5.1 yards per carry to RBs (4th-most). "
            "Derrick Henry projects as an RB1 with 18-22 expected touches against that front. "
            "Green Bay limited RB receiving work to 3.8 targets per game over the prior four weeks."
        ),
    },
    {
        "title": "2024 NFL passing yards leaders",
        "category": "league",
        "content": (
            "Joe Burrow led the NFL with 4,918 passing yards in 2024. "
            "Jared Goff (4,629) and Baker Mayfield (4,500) rounded out the top three. "
            "League average team passing yards per game was 224.6."
        ),
    },
    {
        "title": "Travis Kelce red-zone usage 2024",
        "category": "player",
        "content": (
            "Travis Kelce drew 22 red-zone targets in 2024, 8th among tight ends. "
            "He scored 5 red-zone TDs on a 22.7% red-zone target share inside the 20. "
            "His 12.4 fantasy PPG in half-PPR was TE3 in season-long ranks."
        ),
    },
    {
        "title": "Buffalo Bills offensive pace 2024",
        "category": "team",
        "content": (
            "Buffalo averaged 64.2 plays per game (7th) and 3.04 drives leading to scores per game. "
            "Josh Allen accounted for 42 total TDs (32 pass, 10 rush). "
            "Bills pass rate over expected was +4.2% in neutral script situations."
        ),
    },
    {
        "title": "Injury report: Week 15 2024",
        "category": "injury",
        "content": (
            "Tyreek Hill was listed questionable with a wrist sprain but practiced fully Friday. "
            "Joe Mixon missed practice Wednesday with an ankle issue, then returned limited Thursday. "
            "Mark Andrews was ruled out with an ankle injury before Sunday kickoff."
        ),
    },
    {
        "title": "PPR scoring and roster construction",
        "category": "league",
        "content": (
            "Standard PPR awards 1 point per reception. "
            "In 2024, WRs with 8+ targets per game outscored WRs below 6 targets by 6.1 PPG on average. "
            "Zero-RB builds that waited until rounds 4-5 for a first RB gained +0.8 PPG vs early-RB builds in best-ball data."
        ),
    },
]
