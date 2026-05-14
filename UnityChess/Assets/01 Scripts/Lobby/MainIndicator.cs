using TMPro;
using UnityEngine;

public class MainIndicator : MonoBehaviour
{
    [SerializeField] private TMP_Text playerName;

    void Start()
    {
        bool isloggedin = PlayFabAccountManager.Instance.IsLoggedIn;
        playerName.text = isloggedin ? PlayFabAccountManager.Instance.InGameDisplayName : "Guest";
    }
}
