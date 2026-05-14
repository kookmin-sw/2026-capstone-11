using System.Collections.Generic;
using System.Linq;
using System.IO;
using UnityEditor;
using UnityEngine;
using core.data;

public static class DeckDBGenerator
{
    private const string DeckFolderName = "DeckDB";

    [MenuItem("Tools/Generate DeckDBs")]
    public static void GenerateDeckDBs()
    {
        string[] guids = AssetDatabase.FindAssets("t:CardUnitDB");

        if (guids.Length == 0)
        {
            Debug.LogError("[DeckDBGenerator] CardUnitDB를 찾을 수 없음");
            return;
        }

        // CardUnitDB 로드
        string cardDbPath = AssetDatabase.GUIDToAssetPath(guids[0]);
        CardUnitDB cardUnitDB =
            AssetDatabase.LoadAssetAtPath<CardUnitDB>(cardDbPath);

        if (cardUnitDB == null)
        {
            Debug.LogError("[DeckDBGenerator] CardUnitDB 로드 실패");
            return;
        }

        // CardUnitDB가 있는 폴더
        string parentFolder = Path.GetDirectoryName(cardDbPath)
            ?.Replace("\\", "/");

        // DeckDB 저장 폴더
        string outputFolder = $"{parentFolder}/{DeckFolderName}";

        EnsureFolderExists(outputFolder);

        // leaderId 기준 그룹핑
        var groupedCards = cardUnitDB
            .GetAllCardRows()
            .Where(x => x != null &&
                        !string.IsNullOrWhiteSpace(x.leaderId))
            .GroupBy(x => x.leaderId);

        int generatedCount = 0;

        foreach (var group in groupedCards)
        {
            string leaderId = group.Key;

            List<string> deckCards = new();

            foreach (var card in group)
            {
                deckCards.Add(card.cardId);
            }

            string assetPath =
                $"{outputFolder}/{leaderId}_Deck.asset";

            DeckDB deckDB =
                AssetDatabase.LoadAssetAtPath<DeckDB>(assetPath);

            // 없으면 새로 생성
            if (deckDB == null)
            {
                deckDB = ScriptableObject.CreateInstance<DeckDB>();
                AssetDatabase.CreateAsset(deckDB, assetPath);
            }

            // 데이터 세팅
            deckDB.deckId = leaderId.Split("_")[0];
            deckDB.leaderId = leaderId;
            deckDB.displayName = cardUnitDB.Get(leaderId).Name;
            deckDB.cardIds = deckCards;

            EditorUtility.SetDirty(deckDB);

            generatedCount++;
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log(
            $"[DeckDBGenerator] DeckDB 생성 완료 : {generatedCount}개");
    }

    private static void EnsureFolderExists(string path)
    {
        string[] split = path.Split('/');

        string current = split[0];

        for (int i = 1; i < split.Length; i++)
        {
            string next = $"{current}/{split[i]}";

            if (!AssetDatabase.IsValidFolder(next))
            {
                AssetDatabase.CreateFolder(current, split[i]);
            }

            current = next;
        }
    }
}