using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;
using core.data;

public enum ImportStep
{
    Card,
    Effect,
    Event
}

public class CardDBImporter
{
    [MenuItem("Tools/Import Full Card CSV")]
    public static void Import()
    {
        var cardList = new List<CardRow>();
        var effectList = new List<EffectRow>();
        var eventList = new List<EventRow>();

        foreach (ImportStep s in System.Enum.GetValues(typeof(ImportStep)))
        {
            string path = EditorUtility.OpenFilePanel($"CSV 선택 ({(s == ImportStep.Card ? "Card" : (s == ImportStep.Effect ? "Effect" : "Event"))})", "", "csv");

            if (string.IsNullOrEmpty(path)) return;

            var lines = File.ReadAllLines(path);

            for (int i = 1; i < lines.Length; i++)
            {
                if (string.IsNullOrWhiteSpace(lines[i])) continue;

                var row = SplitCSV(lines[i]);

                try
                {
                    switch (s)
                    {
                        case ImportStep.Card:
                            cardList.Add(new CardRow
                            {
                                cardId = row[0],
                                name = row[1],
                                leaderId = row[2],
                                unitType = ParseRole(row[3]),
                                attack = int.Parse(row[4]),
                                hp = int.Parse(row[5]),
                                effectId = row[6],
                                eventId = row[7]
                            });
                            break;
                        case ImportStep.Effect:
                            effectList.Add(new EffectRow
                            {
                                effectId = row[0],
                                name = row[1],
                                text = row[2]
                            });
                            break;
                        case ImportStep.Event:
                            eventList.Add(new EventRow
                            {
                                eventId = row[0],
                                timing = ParseTiming(row[1]),
                                name = row[2],
                                text = row[3]
                            });
                            break;
                    }
                }
                catch (System.Exception e)
                {
                    Debug.LogError($"라인 {i} 파싱 실패: {e.Message}");
                }
            }
        }

        var db = ScriptableObject.CreateInstance<CardUnitDB>();

        db.SetData(cardList, effectList, eventList);

        string assetPath = "Assets/11 Scriptable Object/CardUnitDB.asset";
        AssetDatabase.CreateAsset(db, assetPath);
        AssetDatabase.SaveAssets();

        Debug.Log($"DB 생성 완료: {assetPath}");
    }

    // CSV 안전 분리 (콤마 포함 문자열 대응)
    private static string[] SplitCSV(string line)
    {
        var result = new List<string>();
        bool inQuotes = false;
        string current = "";

        foreach (char c in line)
        {
            if (c == '"') inQuotes = !inQuotes;
            else if (c == ',' && !inQuotes)
            {
                result.Add(current);
                current = "";
            }
            else current += c;
        }

        result.Add(current);
        return result.ToArray();
    }

    private static string ParseRole(string role)
    {
        switch (role)
        {
            case "L": return "군주";
            case "B": return "비숍";
            case "N": return "나이트";
            case "R": return "룩";
            case "P": return "폰";
            default:
                Debug.LogError($"알 수 없는 Role: {role}");
                return "?";
        }
    }

    private static string ParseTiming(string timing)
    {
        switch (timing)
        {
            case "Always": return "상시";
            case "TurnStart": return "턴 시작";
            case "TurnEnd": return "턴 종료";
            case "OnDestroy": return "파괴 시";
            case "OnMove": return "기본 이동 시";
            default:
                Debug.LogError($"알 수 없는 Timing: {timing}");
                return "알 수 없음";
        }
    }
}