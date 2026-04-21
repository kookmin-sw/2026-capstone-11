using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using Core;
using Core.StateManagement;
using ui.view.board;

public class TestInit : MonoBehaviour
{
    [Header("Snapshot")]
    [SerializeField] private TextAsset sampleSnapshot;

    [Header("Runtime References")]
    [SerializeField] private ChessGameManager gameManager;
    [SerializeField] private GameStateStore stateStore;
    [SerializeField] private BoardView boardView;
    [SerializeField] private Transform handParent;

    [Header("Expectation")]
    [SerializeField] private string expectedActivePlayerId = "Player1";
    [SerializeField] private string localPlayerId = "Player1";
    [SerializeField] private int expectedPlacedUnitCount = 2;
    [SerializeField] private int expectedHandCount = 3;

    [ContextMenu("Run Test Init")]
    public void RunTest()
    {
        StartCoroutine(CoRunTest());
    }

    private IEnumerator CoRunTest()
    {
        if (!ValidateReferences())
            yield break;

        Debug.Log("[TestInit] Apply SampleSnapshot 시작");

        gameManager.ApplySnapshotJson(sampleSnapshot.text);

        // ApplySnapshotJson 내부에서 view refresh가 이벤트/다음 프레임에 연결되어 있을 수 있으므로 1프레임 대기
        yield return null;

        ValidateState();
        ValidateViews();

        Debug.Log("[TestInit] 검증 완료");
    }

    private bool ValidateReferences()
    {
        if (sampleSnapshot == null)
        {
            Debug.LogError("[TestInit] sampleSnapshot is null");
            return false;
        }

        if (gameManager == null)
        {
            Debug.LogError("[TestInit] gameManager is null");
            return false;
        }

        if (stateStore == null)
        {
            Debug.LogError("[TestInit] stateStore is null");
            return false;
        }

        if (boardView == null)
        {
            Debug.LogError("[TestInit] boardView is null");
            return false;
        }

        if (boardView.boardParent == null)
        {
            Debug.LogError("[TestInit] boardView.boardParent is null");
            return false;
        }

        if (handParent == null)
        {
            Debug.LogError("[TestInit] handParent is null");
            return false;
        }

        return true;
    }

    private void ValidateState()
    {
        Debug.Log($"[TestInit] ActivePlayerId = {stateStore.ActivePlayerId}");

        if (stateStore.ActivePlayerId != expectedActivePlayerId)
        {
            Debug.LogError($"[TestInit] ActivePlayerId mismatch. expected={expectedActivePlayerId}, actual={stateStore.ActivePlayerId}");
        }

        var placedUnits = stateStore.GetPlacedUnits();
        var hand = stateStore.GetHand(localPlayerId);

        if (placedUnits.Count != expectedPlacedUnitCount)
        {
            Debug.LogError($"[TestInit] Placed unit count mismatch. expected={expectedPlacedUnitCount}, actual={placedUnits.Count}");
        }

        if (hand.Count != expectedHandCount)
        {
            Debug.LogError($"[TestInit] Hand count mismatch. expected={expectedHandCount}, actual={hand.Count}");
        }

        var placedIds = placedUnits.Select(x => x.id.id).OrderBy(x => x).ToList();
        var handIds = hand.Select(x => x.id).OrderBy(x => x).ToList();

        Debug.Log($"[TestInit] Placed Units = {string.Join(", ", placedIds)}");
        Debug.Log($"[TestInit] Hand = {string.Join(", ", handIds)}");

        AssertSetEquals(
            "[TestInit] Placed Unit IDs",
            placedIds,
            new[] { "C000", "C007" });

        AssertSetEquals(
            "[TestInit] Hand IDs",
            handIds,
            new[] { "C002", "C003", "C004" });
    }

    private void ValidateViews()
    {
        int boardChildCount = boardView.boardParent.transform.childCount;
        int handChildCount = handParent.childCount;

        Debug.Log($"[TestInit] Board View Count = {boardChildCount}");
        Debug.Log($"[TestInit] Hand View Count = {handChildCount}");

        if (boardChildCount != expectedPlacedUnitCount)
        {
            Debug.LogError($"[TestInit] Board view count mismatch. expected={expectedPlacedUnitCount}, actual={boardChildCount}");
        }

        if (handChildCount != expectedHandCount)
        {
            Debug.LogError($"[TestInit] Hand view count mismatch. expected={expectedHandCount}, actual={handChildCount}");
        }

        LogChildren("[TestInit] Board Children", boardView.boardParent.transform);
        LogChildren("[TestInit] Hand Children", handParent);
    }

    private void LogChildren(string label, Transform parent)
    {
        var names = new List<string>();

        for (int i = 0; i < parent.childCount; i++)
        {
            names.Add(parent.GetChild(i).name);
        }

        Debug.Log($"{label} = {string.Join(", ", names)}");
    }

    private void AssertSetEquals(string label, IEnumerable<string> actual, IEnumerable<string> expected)
    {
        var actualSet = new HashSet<string>(actual);
        var expectedSet = new HashSet<string>(expected);

        if (!actualSet.SetEquals(expectedSet))
        {
            Debug.LogError($"{label} mismatch. expected=[{string.Join(", ", expectedSet)}], actual=[{string.Join(", ", actualSet)}]");
        }
    }

    private void Start()
    {
        RunTest();
    }
}