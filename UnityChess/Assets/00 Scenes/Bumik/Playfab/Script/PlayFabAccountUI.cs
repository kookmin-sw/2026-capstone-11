using UnityEngine;
using TMPro;
using System.Linq;
using Unity.VisualScripting;
using System.Text;
using UnityEngine.UI;
using System.Collections.Generic;

public class PlayFabAccountUI : MonoBehaviour
{
    [Header("Register")]
    [SerializeField] private TMP_InputField registerUsernameInput;
    [SerializeField] private TMP_InputField registerDisplaynameInput;
    [SerializeField] private TMP_InputField registerEmailInput;
    [SerializeField] private TMP_InputField registerPasswordInput;
    [SerializeField] private TMP_InputField registerPasswordCheck;
    

    [Header("Login")]
    [SerializeField] private TMP_InputField loginEmailInput;
    [SerializeField] private TMP_InputField loginPasswordInput;



    [Header("Info Field")]
    [SerializeField] private TMP_Text InfoField;

    [Header("API Call Guard Button")]
    [SerializeField] private List<Button> ButtonToGuard;

    private bool APICallGuardFlag = false;

    public void Start()
    {
        UpdateInfoField();
    }

    public void GuardButton()
    {
        APICallGuardFlag = true;
        foreach (var bt in ButtonToGuard) 
            bt.interactable = false;
    }

    public void ReleaseButton()
    {
        APICallGuardFlag = false;
        foreach (var bt in ButtonToGuard) 
            bt.interactable = true;
    }

    public void UpdateInfoField()
    {
        if (!PlayFabAccountManager.Instance.IsLoggedIn)
        {
            InfoField.text = "No Account LogIn";
            return;
        }

        string msg = "PlayFabId="
        + PlayFabAccountManager.Instance.PlayFabId + " \n " 
        + "DisplayName=" 
        + PlayFabAccountManager.Instance.InGameDisplayName + " \n "
        + "SessionTick="
        + PlayFabAccountManager.Instance.SessionTicket + " \n ";

        InfoField.text = msg;
    }

    public void OnClickRegister()
    {
        if (APICallGuardFlag) return;

        string username = registerUsernameInput.text.Trim();
        string displayName = registerDisplaynameInput.text.Trim();
        string email = registerEmailInput.text.Trim();
        string password = registerPasswordInput.text;
        string passwordCheck = registerPasswordCheck.text;

        if (string.IsNullOrWhiteSpace(username) ||
            string.IsNullOrWhiteSpace(email) ||
            string.IsNullOrWhiteSpace(displayName) ||
            string.IsNullOrWhiteSpace(password) ||
            string.IsNullOrWhiteSpace(passwordCheck))
        {
            Debug.Log("회원가입 입력값이 비어 있습니다.");
            return;
        }
        
        if ( displayName.Count() < 3 || displayName.Count() > 25)
        {
            Debug.Log("DisplayName 길이 오류. 3 ~ 25자의 이름 사용");
            return;
        }

        if (!string.Equals(password, passwordCheck))
        {
            Debug.Log("2차 비밀번호 오류");
            return;
        }

        GuardButton();
        PlayFabAccountManager.Instance.Register(
            username,
            displayName,
            email,
            password,
            onSuccess: () =>
            {
                Debug.Log("회원가입 성공");
                UpdateInfoField();
                ReleaseButton();
            },
            onFail: error =>
            {
                Debug.Log("회원가입 실패: " + error);
                UpdateInfoField();
                ReleaseButton();
            });
    }

    public void OnClickLogin()
    {
        if (APICallGuardFlag) return;

        string email = loginEmailInput.text.Trim();
        string password = loginPasswordInput.text;

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
        {
            Debug.Log("로그인 입력값이 비어 있습니다.");
            return;
        }

        GuardButton();
        PlayFabAccountManager.Instance.Login(
            email,
            password,
            onSuccess: () =>
            {
                Debug.Log("로그인 성공");
                UpdateInfoField();
                ReleaseButton();
            },
            onFail: error =>
            {
                Debug.Log("로그인 실패: " + error);
                UpdateInfoField();
                ReleaseButton();
            });
    }
}
