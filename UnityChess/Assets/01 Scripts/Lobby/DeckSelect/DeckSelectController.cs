using System.Collections.Generic;
using System.Linq;
using core.data;
using DG.Tweening;
using TMPro;
using Unity.VisualScripting;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class DeckSelectController : MonoBehaviour
{
    [Header("Deck Data")]
    [SerializeField]
    private List<DeckDB> decks;

    [Header("Card DB")]
    [SerializeField]
    private CardUnitDB cardDB;

    [Header("Sprite DB")]
    [SerializeField]
    private List<Sprite> leaderSprites;

    [SerializeField]
    private List<Sprite> cardSprites;

    [Header("Carousel")]
    [SerializeField]
    private RectTransform content;

    [SerializeField]
    private Transform itemRoot;

    [SerializeField]
    private GameObject leaderItemPrefab;

    [SerializeField]
    private float spacing = 75f;

    [SerializeField]
    private float moveSpeed = 10f;

    [Header("Card List")]
    [SerializeField]
    private Transform cardListRoot;

    [SerializeField]
    private GameObject cardItemPrefab;

    [Header("Selected Display")]
    [SerializeField]
    private SelectedLeaderDisplay selectedLeader;
    [SerializeField]
    private SelectedLeaderDisplay lookingLeader;
    [SerializeField]
    private TMP_Text lookingDeckName;

    [Header("Buttons")]
    [SerializeField]
    private Button applyButton;

    private List<GameObject> leaderItems = new();
    private List<DeckCardItem> cardItems = new(); 

    private Dictionary<string, Sprite> leaderSpriteMap = new();

    private Dictionary<string, Sprite> cardSpriteMap = new();

    private int currentIndex;

    private int appliedIndex;

    private Vector2 targetPosition;

    private void Awake()
    {
        BuildSpriteMaps();
    }

    private void Start()
    {
        BuildCarousel();
        BuildCardList();

        appliedIndex = LoadSavedDeckIndex();

        currentIndex = appliedIndex;

        Select(currentIndex, true);

        ApplyVisual();
    }

    // ------------------------
    // Input
    // ------------------------

    public void OnMove(InputAction.CallbackContext ctx)
    {
        if (!ctx.performed)
            return;

        Vector2 value = ctx.ReadValue<Vector2>();

        if (value.x > 0.5f)
        {
            MoveRight();
        }
        else if (value.x < -0.5f)
        {
            MoveLeft();
        }
    }

    public void MoveLeft()
    {
        Select(currentIndex - 1);
    }

    public void MoveRight()
    {
        Select(currentIndex + 1);
    }

    // ------------------------
    // Selection
    // ------------------------

    public void Select(int index)
    {
        Select(index, false);
    }

    private void Select(int index, bool instant)
    {
        if (decks.Count == 0)
            return;

        currentIndex = (index + decks.Count) % decks.Count;

        targetPosition = new Vector2(-currentIndex * spacing, 0);

        if (instant)
        {
            content.anchoredPosition = targetPosition;
        }
        else
        {
            content.DOAnchorPos(targetPosition, 0.25f).SetEase(Ease.OutCubic);
        }

        RefreshSelection();
        RefreshCardList();
        RefreshApplyButton();
    }

    // ------------------------
    // Build
    // ------------------------

    private void BuildSpriteMaps()
    {
        leaderSpriteMap.Clear();

        for (int i = 0; i < decks.Count; i++)
        {
            if (leaderSprites[i] == null)
                continue;

            leaderSpriteMap[decks[i].leaderId] = leaderSprites[i];
        }

        cardSpriteMap.Clear();

        for (int i = 0; i < decks.Count; i++)
        {
            var cards = decks[i].cardIds;

            for (int j = 0; j < cards.Count; j++)
            {
                cardSpriteMap[cards[j]] = cardSprites[i * cards.Count + j];
            }
        }
    }

    private void BuildCarousel()
    {
        leaderItems = new List<GameObject>();

        for (int i = 0; i < decks.Count; i++)
        {
            var obj = Instantiate(leaderItemPrefab, content);

            var rect = obj.GetComponent<RectTransform>();

            // 여기서 딱 1번
            rect.anchoredPosition = new Vector2(i * spacing, 0);

            rect.localScale = Vector3.one;

            var item = obj.GetComponent<LeaderCarouselItem>();

            leaderSpriteMap.TryGetValue(decks[i].leaderId, out var sprite);

            item.Bind(i, sprite);

            leaderItems.Add(obj);
        }
    }

    private void BuildCardList()
    {
        int maxCardCount = decks.Max(x => x.cardIds.Count);

        for (int i = 0; i < maxCardCount; i++)
        {
            var obj = Instantiate(cardItemPrefab, cardListRoot);

            obj.SetActive(false);

            cardItems.Add(obj.GetComponent<DeckCardItem>());
        }
    }

    // ------------------------
    // Refresh
    // ------------------------

    private void RefreshSelection()
    {
        for (int i = 0; i < leaderItems.Count; i++)
        {
            bool focused = i == currentIndex;

            float scale = focused ? 1.15f : 0.8f;

            float y = focused ? 20f : 0f;

            var rect = leaderItems[i].GetComponent<RectTransform>();

            rect.localScale = Vector3.one * scale;

            rect.anchoredPosition = new Vector2(rect.anchoredPosition.x, y);
        }

        var deck = decks[currentIndex];

        lookingDeckName.text = deck.displayName;
        
        leaderSpriteMap.TryGetValue(deck.leaderId, out var sprite);
        
        lookingLeader.Bind(sprite);
    }

    private void RefreshCardList()
    {
        var deck = decks[currentIndex];

        for (int i = 0; i < cardItems.Count; i++)
        {
            bool active = i < deck.cardIds.Count;

            cardItems[i].gameObject.SetActive(active);

            if (!active)
                continue;

            var card = deck.cardIds[i];

            cardSpriteMap.TryGetValue(card, out var sprite);

            cardItems[i].Bind(cardDB.Get(card), sprite);
        }
    }

    private void RefreshApplyButton()
    {
        applyButton.interactable = currentIndex != appliedIndex;
    }

    // ------------------------
    // Apply
    // ------------------------

    public void ApplySelection()
    {
        appliedIndex = currentIndex;

        SaveSelectedDeckIndex(appliedIndex);

        ApplyVisual();

        RefreshApplyButton();
    }

    private void ApplyVisual()
    {
        var deck = decks[appliedIndex];

        leaderSpriteMap.TryGetValue(deck.leaderId, out var sprite);
        selectedLeader.Bind(sprite);
    }

    public void CloseMenu()
    {
        currentIndex = appliedIndex;

        Select(currentIndex, true);

        gameObject.SetActive(false);
    }

    // ------------------------
    // Save
    // ------------------------

    private int LoadSavedDeckIndex() => PlayerPrefs.GetInt("SelectedDeckIndex", 0);

    private void SaveSelectedDeckIndex(int index)
    {
        PlayerPrefs.SetInt("SelectedDeckIndex", index);

        PlayerPrefs.Save();
    }
}